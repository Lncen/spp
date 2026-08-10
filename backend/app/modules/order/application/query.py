"""订单模块：查询应用服务"""

import uuid

from sqlmodel import Session, select

from app.modules.order.models import Order
from app.modules.order.repositories.order import (
    get_order,
    get_user_order,
    list_orders,
    list_user_orders,
)
from app.modules.order.schemas import OrderListItem, OrderPublic
from app.modules.user.models import User

__all__ = [
    "get_order",
    "get_user_order",
    "list_orders",
    "list_user_orders",
    "to_order_list_item",
    "to_order_public",
]


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
