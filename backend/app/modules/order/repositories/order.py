"""订单模块：数据访问层"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, delete, func, or_, select

from app.modules.order.domain.constants import (
    ACTIVE_ORDER_STATUSES,
    OrderStatus,
)
from app.modules.order.domain.validation import (
    _normalize_params,
    _validate_and_build_params,
    _validate_product_sellable,
    _validate_quantity,
    normalize_param_value,
)
from app.modules.order.models import Order, OrderParam
from app.modules.order.schemas import OrderCreate
from app.modules.product.product.models import (
    Product,
    ProductBuyParam,
    ProductFulfillment,
    ProductInventory,
    ProductSupplier,
)
from app.modules.supplier.models import Supplier
from app.modules.supplier.schemas import PlatformEnum


def get_order(*, session: Session, order_id: uuid.UUID) -> Order:
    """按 ID 获取订单，不存在时抛出 404"""
    db_order = session.get(Order, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return db_order


def get_user_order(
    *, session: Session, order_id: uuid.UUID, user_id: uuid.UUID
) -> Order:
    """获取当前用户自己的订单，越权访问按不存在处理"""
    db_order = get_order(session=session, order_id=order_id)
    if db_order.user_id != user_id:
        raise HTTPException(status_code=404, detail="订单不存在")
    return db_order


def list_orders(
    *,
    session: Session,
    skip: int,
    limit: int,
    status: OrderStatus | None = None,
    user_id: uuid.UUID | None = None,
    keyword: str | None = None,
) -> tuple[list[Order], int]:
    """分页查询全部订单，可按状态、用户与关键字过滤

    keyword 精确匹配订单 ID、订单号或下单参数值。
    """
    conditions = []
    if status is not None:
        conditions.append(Order.status == status)
    if user_id is not None:
        conditions.append(Order.user_id == user_id)
    if keyword:
        keyword_conditions = [
            Order.order_no == keyword,
            Order.id.in_(
                select(OrderParam.order_id).where(
                    OrderParam.value == keyword
                )
            ),
        ]
        try:
            order_id = uuid.UUID(keyword)
        except ValueError:
            pass
        else:
            keyword_conditions.append(Order.id == order_id)
        conditions.append(or_(*keyword_conditions))
    count = session.exec(
        select(func.count()).select_from(Order).where(*conditions)
    ).one()
    statement = (
        select(Order)
        .where(*conditions)
        .order_by(col(Order.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all()), count


def list_user_orders(
    *,
    session: Session,
    user_id: uuid.UUID,
    skip: int,
    limit: int,
) -> tuple[list[Order], int]:
    """分页查询当前用户自己的订单"""
    conditions = [Order.user_id == user_id]
    count = session.exec(
        select(func.count()).select_from(Order).where(*conditions)
    ).one()
    statement = (
        select(Order)
        .where(*conditions)
        .order_by(col(Order.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all()), count


def ensure_no_duplicate_active_order(
    *,
    session: Session,
    user_id: uuid.UUID,
    product_id: uuid.UUID,
    params: dict[str, Any],
) -> None:
    """同用户同商品同参数且未完成的订单禁止重复创建，数量不参与比较"""
    normalized = _normalize_params(params)
    statement = select(Order).where(
        Order.user_id == user_id,
        Order.product_id == product_id,
        Order.status.in_(ACTIVE_ORDER_STATUSES),
    )
    for order in session.exec(statement).all():
        if _normalize_params(order.params) == normalized:
            raise HTTPException(
                status_code=400,
                detail="该商品相同参数订单未完成，禁止重复下单",
            )


def _validate_supplier_available(
    *, session: Session, product: Product
) -> ProductSupplier | None:
    """校验商品供应商可用；自营商品跳过，返回货源记录供订单快照"""
    supplier_sku = session.exec(
        select(ProductSupplier).where(ProductSupplier.product_id == product.id)
    ).first()
    if supplier_sku is None or supplier_sku.supplier_id is None:
        return supplier_sku
    supplier = session.get(Supplier, supplier_sku.supplier_id)
    if supplier is None:
        return supplier_sku
    if supplier.platform == PlatformEnum.SELF:
        return supplier_sku
    if not supplier.is_active or supplier.status != "active":
        raise HTTPException(status_code=400, detail="商品暂不可下单，请稍后重试")
    return supplier_sku


def _load_order_snapshot(
    *,
    session: Session,
    order_in: OrderCreate,
) -> dict[str, Any]:
    """校验商品、供应商、数量与参数，返回不含价格的订单快照字段"""
    product = session.get(Product, order_in.product_id)
    if not product:
        raise HTTPException(status_code=400, detail="商品不存在")

    inventory = session.exec(
        select(ProductInventory).where(ProductInventory.product_id == product.id)
    ).first()
    fulfillment = session.exec(
        select(ProductFulfillment).where(ProductFulfillment.product_id == product.id)
    ).first()

    _validate_product_sellable(product=product, inventory=inventory, fulfillment=fulfillment)
    supplier_sku = _validate_supplier_available(session=session, product=product)
    _validate_quantity(inventory=inventory, quantity=order_in.quantity)

    buy_params = session.exec(
        select(ProductBuyParam).where(ProductBuyParam.product_id == product.id)
    ).all()
    params_snapshot = _validate_and_build_params(
        params=order_in.params,
        buy_params=buy_params,
    )
    return {
        "product": product,
        "inventory": inventory,
        "fulfillment": fulfillment,
        "supplier_id": supplier_sku.supplier_id if supplier_sku else None,
        "sku_id": supplier_sku.sku_id if supplier_sku else None,
        "quantity": order_in.quantity,
        "params": params_snapshot,
    }


def sync_order_params(*, session: Session, db_order: Order) -> None:
    """展开订单 params 写入 order_params，保持按参数值查询可命中"""
    session.exec(delete(OrderParam).where(OrderParam.order_id == db_order.id))
    rows = [
        OrderParam(
            order_id=db_order.id,
            key=str(key),
            value=normalize_param_value(value),
        )
        for key, value in (db_order.params or {}).items()
    ]
    session.add_all(rows)


def purge_completed_orders(
    *,
    session: Session,
    before: datetime,
    limit: int,
) -> int:
    """物理删除终态订单（已完成/已退单/已退款）中最后更新早于 before 的订单。

    连同订单参数一并删除，返回删除订单条数；钱包流水不在删除范围。
    显式先删 order_params 再删 orders（不依赖数据库级联配置），分批由调用方控制。
    """
    ids = session.exec(
        select(Order.id)
        .where(
            Order.status.in_(
                (
                    OrderStatus.COMPLETED,
                    OrderStatus.CANCELED,
                    OrderStatus.REFUNDED,
                )
            ),
            col(Order.updated_at) < before,
        )
        .order_by(col(Order.updated_at).asc())
        .limit(limit)
    ).all()
    if not ids:
        return 0
    session.exec(delete(OrderParam).where(OrderParam.order_id.in_(ids)))
    session.exec(delete(Order).where(Order.id.in_(ids)))
    session.commit()
    return len(ids)
