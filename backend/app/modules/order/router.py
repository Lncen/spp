"""订单模块：路由层"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_current_active_superuser,
)
from app.modules.order.constants import OrderStatus
from app.modules.order.schemas import OrderCreate, OrderPublic, OrdersPublic
from app.modules.order.service import (
    cancel_order,
    create_order,
    fulfill_order,
    get_order,
    get_user_order,
    list_orders,
    list_user_orders,
    refund_order,
)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=OrderPublic)
def create_user_order(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: OrderCreate,
) -> Any:
    """创建订单（下单即扣款）"""
    return create_order(session=session, user=current_user, order_in=body)


@router.get("/me", response_model=OrdersPublic)
def read_user_orders(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """查看当前用户订单列表"""
    orders, count = list_user_orders(
        session=session,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return OrdersPublic(
        data=[OrderPublic.model_validate(order) for order in orders],
        count=count,
    )


@router.get("/me/{order_id}", response_model=OrderPublic)
def read_user_order(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    order_id: uuid.UUID,
) -> Any:
    """查看当前用户的单个订单"""
    return get_user_order(
        session=session,
        order_id=order_id,
        user_id=current_user.id,
    )


@router.post("/me/{order_id}/cancel", response_model=OrderPublic)
def cancel_user_order(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    order_id: uuid.UUID,
) -> Any:
    """用户取消待处理订单"""
    db_order = get_user_order(
        session=session,
        order_id=order_id,
        user_id=current_user.id,
    )
    return cancel_order(
        session=session,
        db_order=db_order,
        operator_id=current_user.id,
    )


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=OrdersPublic,
)
def read_orders(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    status: OrderStatus | None = None,
) -> Any:
    """查看全部订单（仅超级管理员可用）"""
    orders, count = list_orders(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
    )
    return OrdersPublic(
        data=[OrderPublic.model_validate(order) for order in orders],
        count=count,
    )


@router.get(
    "/{order_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=OrderPublic,
)
def read_order(*, session: SessionDep, order_id: uuid.UUID) -> Any:
    """查看单个订单（仅超级管理员可用）"""
    return get_order(session=session, order_id=order_id)


@router.post(
    "/{order_id}/fulfill",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=OrderPublic,
)
def fulfill_order_api(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    order_id: uuid.UUID,
) -> Any:
    """履约订单（仅超级管理员可用）"""
    db_order = get_order(session=session, order_id=order_id)
    return fulfill_order(
        session=session,
        db_order=db_order,
        operator_id=current_user.id,
    )


@router.post(
    "/{order_id}/cancel",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=OrderPublic,
)
def cancel_order_api(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    order_id: uuid.UUID,
) -> Any:
    """管理员取消待处理订单"""
    db_order = get_order(session=session, order_id=order_id)
    return cancel_order(
        session=session,
        db_order=db_order,
        operator_id=current_user.id,
    )


@router.post(
    "/{order_id}/refund",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=OrderPublic,
)
def refund_order_api(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    order_id: uuid.UUID,
) -> Any:
    """整单退款（仅超级管理员可用）"""
    db_order = get_order(session=session, order_id=order_id)
    return refund_order(
        session=session,
        db_order=db_order,
        operator_id=current_user.id,
    )
