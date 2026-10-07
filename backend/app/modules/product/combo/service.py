"""商品模块：用户组合业务逻辑层"""

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, delete, func, select

from app.modules.product.combo.models import ProductCombo, ProductComboItem
from app.modules.product.combo.schemas import (
    ProductComboCreate,
    ProductComboItemCreate,
    ProductComboUpdate,
)
from app.modules.product.product.models import Product


def _validate_items(*, session: Session, items: list[ProductComboItemCreate]) -> None:
    """校验组合明细：商品不能重复，且必须存在"""
    product_ids = [item.product_id for item in items]
    if len(product_ids) != len(set(product_ids)):
        raise HTTPException(status_code=400, detail="组合内商品不能重复")
    distinct_ids = set(product_ids)
    products = session.exec(
        select(Product).where(col(Product.id).in_(distinct_ids))
    ).all()
    if {product.id for product in products} != distinct_ids:
        raise HTTPException(status_code=400, detail="组合包含不存在的商品")


def _check_name_unique(
    *,
    session: Session,
    user_id: uuid.UUID,
    name: str,
    exclude_id: uuid.UUID | None = None,
) -> None:
    """同一用户下组合名称唯一"""
    db_combo = session.exec(
        select(ProductCombo).where(
            ProductCombo.user_id == user_id,
            ProductCombo.name == name,
        )
    ).first()
    if db_combo and (exclude_id is None or db_combo.id != exclude_id):
        raise HTTPException(status_code=400, detail="组合名称已存在")


def _replace_items(
    *,
    session: Session,
    combo_id: uuid.UUID,
    items: list[ProductComboItemCreate],
) -> None:
    """整体替换组合明细，展示顺序取提交顺序"""
    session.execute(
        delete(ProductComboItem).where(ProductComboItem.combo_id == combo_id)
    )
    session.add_all(
        [
            ProductComboItem(
                combo_id=combo_id,
                product_id=item.product_id,
                mode=item.mode,
                quantity=item.quantity,
                min_quantity=item.min_quantity,
                max_quantity=item.max_quantity,
                sort=index,
            )
            for index, item in enumerate(items)
        ]
    )


def get_combo(
    *, session: Session, user_id: uuid.UUID, combo_id: uuid.UUID
) -> ProductCombo:
    """获取当前用户自己的组合，越权访问按不存在处理"""
    db_combo = session.get(ProductCombo, combo_id)
    if not db_combo or db_combo.user_id != user_id:
        raise HTTPException(status_code=404, detail="组合不存在")
    return db_combo


def list_combos(
    *,
    session: Session,
    user_id: uuid.UUID,
    skip: int,
    limit: int,
) -> tuple[list[ProductCombo], int]:
    """分页查询当前用户组合，按创建时间倒序"""
    conditions = [ProductCombo.user_id == user_id]
    count = session.exec(
        select(func.count()).select_from(ProductCombo).where(*conditions)
    ).one()
    statement = (
        select(ProductCombo)
        .where(*conditions)
        .order_by(col(ProductCombo.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all()), count


def list_combo_items(
    *, session: Session, combo_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[ProductComboItem]]:
    """批量查询组合明细，按组合分组，组内按 sort 升序"""
    if not combo_ids:
        return {}
    rows = session.exec(
        select(ProductComboItem)
        .where(col(ProductComboItem.combo_id).in_(combo_ids))
        .order_by(
            col(ProductComboItem.sort).asc(),
            col(ProductComboItem.created_at).asc(),
        )
    ).all()
    items_map: dict[uuid.UUID, list[ProductComboItem]] = {}
    for row in rows:
        items_map.setdefault(row.combo_id, []).append(row)
    return items_map


def create_combo(
    *,
    session: Session,
    user_id: uuid.UUID,
    combo_in: ProductComboCreate,
) -> ProductCombo:
    """创建组合及其明细"""
    _check_name_unique(session=session, user_id=user_id, name=combo_in.name)
    _validate_items(session=session, items=combo_in.items)
    db_combo = ProductCombo(
        user_id=user_id,
        name=combo_in.name,
        remark=combo_in.remark,
    )
    session.add(db_combo)
    try:
        session.flush()
    except IntegrityError:
        # 并发下唯一约束兜底
        session.rollback()
        raise HTTPException(status_code=400, detail="组合名称已存在")
    _replace_items(session=session, combo_id=db_combo.id, items=combo_in.items)
    session.commit()
    session.refresh(db_combo)
    return db_combo


def update_combo(
    *,
    session: Session,
    user_id: uuid.UUID,
    combo_id: uuid.UUID,
    combo_in: ProductComboUpdate,
) -> ProductCombo:
    """更新组合：名称/备注部分更新，明细传入时整体替换"""
    db_combo = get_combo(session=session, user_id=user_id, combo_id=combo_id)
    update_dict = combo_in.model_dump(exclude_unset=True)
    if combo_in.name is not None:
        _check_name_unique(
            session=session,
            user_id=user_id,
            name=combo_in.name,
            exclude_id=combo_id,
        )
        db_combo.name = combo_in.name
    # 备注显式传 null 表示清空
    if "remark" in update_dict:
        db_combo.remark = combo_in.remark
    if combo_in.items is not None:
        _validate_items(session=session, items=combo_in.items)
        _replace_items(session=session, combo_id=combo_id, items=combo_in.items)
    session.add(db_combo)
    session.commit()
    session.refresh(db_combo)
    return db_combo


def delete_combo(*, session: Session, user_id: uuid.UUID, combo_id: uuid.UUID) -> None:
    """删除组合及其明细"""
    db_combo = get_combo(session=session, user_id=user_id, combo_id=combo_id)
    session.execute(
        delete(ProductComboItem).where(ProductComboItem.combo_id == combo_id)
    )
    session.delete(db_combo)
    session.commit()
