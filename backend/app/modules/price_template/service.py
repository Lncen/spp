"""价格模板模块：业务逻辑层"""

import uuid
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.modules.level.models import UserLevel
from app.modules.price_template.constants import (
    DEFAULT_DISCOUNT_RATE,
    LEVEL_MAX,
    LEVEL_MIN,
    MONEY_PRECISION,
)
from app.modules.price_template.models import PriceTemplate, PriceTemplateRule
from app.modules.price_template.schemas import (
    PriceTemplateCreate,
    PriceTemplateRuleIn,
    PriceTemplateUpdate,
)


def _check_name_unique(
    *, session: Session, name: str, exclude_id: uuid.UUID | None = None
) -> None:
    """校验模板名称唯一"""
    db_template = session.exec(
        select(PriceTemplate).where(PriceTemplate.name == name)
    ).first()
    if db_template and (exclude_id is None or db_template.id != exclude_id):
        raise HTTPException(status_code=400, detail="模板名称已存在")


def _resolve_level_ids(
    *, session: Session, levels: list[int]
) -> dict[int, uuid.UUID]:
    """按等级编号批量解析用户等级 UUID"""
    rows = session.exec(
        select(UserLevel).where(UserLevel.level.in_(levels))
    ).all()
    resolved = {row.level: row.id for row in rows if row.id}
    missing = sorted(set(levels) - set(resolved))
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"用户等级不存在: {', '.join(str(level) for level in missing)}",
        )
    return resolved


def _replace_rules(
    *,
    session: Session,
    template: PriceTemplate,
    rules: list[PriceTemplateRuleIn],
) -> None:
    """重建模板的 1-10 等级折扣，未传入等级自动按 15 折补齐"""
    level_ids = _resolve_level_ids(
        session=session,
        levels=list(range(LEVEL_MIN, LEVEL_MAX + 1)),
    )
    discount_by_level = {rule.level: rule.discount_rate for rule in rules}

    old_rules = session.exec(
        select(PriceTemplateRule).where(
            PriceTemplateRule.price_template_id == template.id
        )
    ).all()
    for old_rule in old_rules:
        session.delete(old_rule)
    session.flush()

    template_id = template.id
    for level, level_id in level_ids.items():
        session.add(
            PriceTemplateRule(
                price_template_id=template_id,
                level_id=level_id,
                discount_rate=discount_by_level.get(level, DEFAULT_DISCOUNT_RATE),
            )
        )
    session.commit()


def _clear_default_flag(*, session: Session) -> None:
    """将其他模板的默认标记清空，保证同一时间只有一个默认模板"""
    defaults = session.exec(
        select(PriceTemplate).where(PriceTemplate.is_default)
    ).all()
    for row in defaults:
        row.is_default = False
        session.add(row)


def create_price_template(
    *, session: Session, template_in: PriceTemplateCreate
) -> PriceTemplate:
    """创建价格模板，并为 1-10 等级补齐折扣规则"""
    _check_name_unique(session=session, name=template_in.name)
    if template_in.is_default:
        _clear_default_flag(session=session)
    db_template = PriceTemplate(
        name=template_in.name,
        description=template_in.description,
        is_default=template_in.is_default,
    )
    session.add(db_template)
    session.commit()
    session.refresh(db_template)
    _replace_rules(session=session, template=db_template, rules=template_in.rules)
    session.refresh(db_template)
    return db_template


def get_price_template(
    *, session: Session, template_id: uuid.UUID
) -> PriceTemplate:
    """根据 ID 获取价格模板"""
    db_template = session.get(PriceTemplate, template_id)
    if not db_template:
        raise HTTPException(status_code=404, detail="价格模板不存在")
    return db_template


def get_default_price_template(*, session: Session) -> PriceTemplate | None:
    """获取当前启用的默认价格模板"""
    return session.exec(
        select(PriceTemplate).where(
            PriceTemplate.is_default,
            PriceTemplate.is_active,
        )
    ).first()


def get_all_price_templates(
    *, session: Session, skip: int, limit: int
) -> list[PriceTemplate]:
    """获取价格模板列表"""
    statement = (
        select(PriceTemplate)
        .order_by(col(PriceTemplate.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    return session.exec(statement).all()


def get_price_template_count(*, session: Session) -> int:
    """获取价格模板总数"""
    statement = select(func.count()).select_from(PriceTemplate)
    return session.exec(statement).one()


def _upsert_rules(
    *,
    session: Session,
    template: PriceTemplate,
    rules: list[PriceTemplateRuleIn],
) -> None:
    """仅覆盖传入等级的折扣，其他等级保留原折扣"""
    levels = list({rule.level for rule in rules})
    level_ids = _resolve_level_ids(session=session, levels=levels)
    for rule_in in rules:
        level_id = level_ids[rule_in.level]
        existing = session.exec(
            select(PriceTemplateRule).where(
                PriceTemplateRule.price_template_id == template.id,
                PriceTemplateRule.level_id == level_id,
            )
        ).first()
        if existing:
            existing.discount_rate = rule_in.discount_rate
            session.add(existing)
        else:
            session.add(
                PriceTemplateRule(
                    price_template_id=template.id,
                    level_id=level_id,
                    discount_rate=rule_in.discount_rate,
                )
            )
    session.commit()


def update_price_template(
    *,
    session: Session,
    template_id: uuid.UUID,
    template_in: PriceTemplateUpdate,
) -> PriceTemplate:
    """更新价格模板；传入的规则覆盖对应等级，未传等级保留"""
    db_template = get_price_template(session=session, template_id=template_id)
    rules_in = template_in.rules
    update_dict = template_in.model_dump(exclude_unset=True, exclude={"rules"})

    # 如果设置了 is_default=True，先将其他模板设为非默认
    if update_dict.get("is_default") is True:
        _clear_default_flag(session=session)

    new_name = update_dict.get("name")
    if new_name is not None:
        _check_name_unique(
            session=session,
            name=new_name,
            exclude_id=template_id,
        )

    db_template.sqlmodel_update(update_dict)
    session.add(db_template)
    session.commit()
    session.refresh(db_template)

    if rules_in is not None:
        _upsert_rules(session=session, template=db_template, rules=rules_in)
        session.refresh(db_template)
    return db_template


def delete_price_template(*, session: Session, template_id: uuid.UUID) -> None:
    """删除价格模板，规则级联删除"""
    db_template = get_price_template(session=session, template_id=template_id)
    session.delete(db_template)
    session.commit()


def get_rules_by_template_id(
    *, session: Session, template_id: uuid.UUID
) -> list[tuple[PriceTemplateRule, int]]:
    """获取模板的等级折扣规则（按等级编号升序）"""
    statement = (
        select(PriceTemplateRule, UserLevel.level)
        .join(UserLevel, UserLevel.id == PriceTemplateRule.level_id)
        .where(PriceTemplateRule.price_template_id == template_id)
        .order_by(UserLevel.level)
    )
    return session.exec(statement).all()


def get_rules_by_template_ids(
    *, session: Session, template_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[tuple[PriceTemplateRule, int]]]:
    """批量获取多个模板的等级折扣规则，避免 N+1 查询"""
    if not template_ids:
        return {}
    statement = (
        select(PriceTemplateRule, UserLevel.level)
        .join(UserLevel, UserLevel.id == PriceTemplateRule.level_id)
        .where(PriceTemplateRule.price_template_id.in_(template_ids))
        .order_by(UserLevel.level)
    )
    result: dict[uuid.UUID, list[tuple[PriceTemplateRule, int]]] = {}
    for rule, level in session.exec(statement).all():
        result.setdefault(rule.price_template_id, []).append((rule, level))
    return result


def get_user_price(
    *,
    session: Session,
    base_price: Decimal,
    price_template_id: uuid.UUID | None,
    user_level_id: uuid.UUID | None,
) -> Decimal:
    """按用户等级计算商品用户价；无模板/未启用时按基准价，规则缺失时按 15 折"""
    if price_template_id is None or user_level_id is None:
        return base_price.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)

    db_template = session.get(PriceTemplate, price_template_id)
    if not db_template or not db_template.is_active:
        return base_price.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)

    rule = session.exec(
        select(PriceTemplateRule).where(
            PriceTemplateRule.price_template_id == price_template_id,
            PriceTemplateRule.level_id == user_level_id,
        )
    ).first()
    rate = rule.discount_rate if rule else DEFAULT_DISCOUNT_RATE
    return (base_price * rate).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)
