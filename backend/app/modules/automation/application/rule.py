"""自动化模块：自动化规则应用服务

按业务能力归组：规则创建、更新、启停、删除与查询。
"""

import uuid

from sqlalchemy.orm import Session

from app.modules.automation.domain.validation import validate_rule_config
from app.modules.automation.infrastructure.executors import get_executor
from app.modules.automation.models import AutomationRule
from app.modules.automation.repositories.rule import (
    count_rules,
    get_rule_or_404,
    list_rules,
)
from app.modules.automation.repositories.rule import (
    create_rule as create_rule_record,
)
from app.modules.automation.schemas import (
    AutomationRuleCreate,
    AutomationRulePublic,
    AutomationRulesPublic,
    AutomationRuleUpdate,
)


def create_automation_rule(
    *,
    session: Session,
    rule_in: AutomationRuleCreate,
) -> AutomationRule:
    """创建自动化规则，动作类型必须已注册 Executor，否则抛出 ValueError。"""
    validate_rule_config(rule_in.config)
    get_executor(rule_in.action_type)
    rule = create_rule_record(
        session=session,
        name=rule_in.name,
        description=rule_in.description,
        event_type=rule_in.event_type,
        action_type=rule_in.action_type,
        config=rule_in.config,
        priority=rule_in.priority,
        is_active=rule_in.is_active,
    )
    session.commit()
    session.refresh(rule)
    return rule


def update_automation_rule(
    *,
    session: Session,
    rule_id: uuid.UUID,
    rule_in: AutomationRuleUpdate,
) -> AutomationRule:
    """更新自动化规则，修改动作类型时校验已注册 Executor。"""
    rule = get_rule_or_404(session=session, rule_id=rule_id)
    update_dict = rule_in.model_dump(exclude_unset=True)
    action_type = update_dict.get("action_type")
    if action_type is not None:
        get_executor(action_type)
    if "config" in update_dict and update_dict["config"] is not None:
        validate_rule_config(update_dict["config"])

    nullable_update_fields = {"description"}
    update_dict = {
        key: value
        for key, value in update_dict.items()
        if value is not None or key in nullable_update_fields
    }
    for field, value in update_dict.items():
        setattr(rule, field, value)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def toggle_automation_rule(
    *,
    session: Session,
    rule_id: uuid.UUID,
) -> AutomationRule:
    """启用或停用自动化规则。"""
    rule = get_rule_or_404(session=session, rule_id=rule_id)
    rule.toggle_active()
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def delete_automation_rule(*, session: Session, rule_id: uuid.UUID) -> None:
    """删除自动化规则。"""
    rule = get_rule_or_404(session=session, rule_id=rule_id)
    session.delete(rule)
    session.commit()


def list_automation_rules(
    *,
    session: Session,
    skip: int,
    limit: int,
) -> AutomationRulesPublic:
    """分页获取自动化规则列表。"""
    count = count_rules(session=session)
    rules = list_rules(session=session, skip=skip, limit=limit)
    return AutomationRulesPublic(
        data=[to_automation_rule_public(rule) for rule in rules],
        count=count,
    )


def get_automation_rule_public(
    *,
    session: Session,
    rule_id: uuid.UUID,
) -> AutomationRulePublic:
    """按 ID 获取自动化规则公开响应。"""
    return to_automation_rule_public(
        get_rule_or_404(session=session, rule_id=rule_id)
    )


def to_automation_rule_public(rule: AutomationRule) -> AutomationRulePublic:
    """将 AutomationRule 转为公开响应模型。"""
    return AutomationRulePublic.model_validate(rule)
