"""订单模块：查询辅助函数"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.modules.order.constants import OrderStatus
from app.modules.order.models import Order, OrderParam
from app.modules.order.schemas import OrderListItem, OrderPublic
from app.modules.user.models import User


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
    param_value: str | None = None,
) -> tuple[list[Order], int]:
    """分页查询全部订单，可按状态与用户过滤"""
    conditions = []
    if status is not None:
        conditions.append(Order.status == status)
    if user_id is not None:
        conditions.append(Order.user_id == user_id)
    if param_value is not None:
        conditions.append(
            Order.id.in_(
                select(OrderParam.order_id).where(
                    OrderParam.value == param_value
                )
            )
        )
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


def _username_by_id(
    *, session: Session, orders: list[Order]
) -> dict[uuid.UUID, str | None]:
    """按用户 ID 批量查询下单用户 username"""
    if not orders:
        return {}
    user_ids = {order.user_id for order in orders}
    users = session.exec(select(User).where(User.id.in_(user_ids))).all()
    return {user.id: user.username for user in users}


def to_order_public(*, session: Session, orders: list[Order]) -> list[OrderPublic]:
    """将订单模型转换为详情响应模型，并附加下单用户 username"""
    if not orders:
        return []
    username_by_id = _username_by_id(session=session, orders=orders)
    result: list[OrderPublic] = []
    for order in orders:
        data = OrderPublic.model_validate(order).model_dump()
        data["username"] = username_by_id.get(order.user_id)
        result.append(OrderPublic.model_validate(data))
    return result


def to_order_list_item(
    *, session: Session, orders: list[Order]
) -> list[OrderListItem]:
    """将订单模型转换为列表响应模型，仅包含列表所需字段"""
    if not orders:
        return []
    username_by_id = _username_by_id(session=session, orders=orders)
    result: list[OrderListItem] = []
    for order in orders:
        data = OrderListItem.model_validate(order).model_dump()
        data["username"] = username_by_id.get(order.user_id)
        result.append(OrderListItem.model_validate(data))
    return result


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
