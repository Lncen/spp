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
from app.modules.order.schemas import (
    AdminOrdersCreate,
    AdminOrdersPreviewPublic,
    AdminOrdersPublic,
    OrderCreate,
    OrderPublic,
    OrdersPublic,
)
from app.modules.order.service import (
    cancel_order,
    create_admin_orders,
    create_order,
    fulfill_order,
    get_order,
    get_user_order,
    list_orders,
    list_user_orders,
    preview_admin_orders,
    refund_order,
    sync_order_status,
    to_order_public,
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
    db_order = create_order(session=session, user=current_user, order_in=body)
    return to_order_public(session=session, orders=[db_order])[0]


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
        data=to_order_public(session=session, orders=orders),
        count=count,
    )


@router.post(
    "/admin",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AdminOrdersPublic,
)
def create_admin_orders_api(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: AdminOrdersCreate,
) -> Any:
    """管理员批量下单（仅超管），跳过钱包与余额校验"""
    return create_admin_orders(
        session=session,
        operator=current_user,
        body=body,
    )


@router.post(
    "/admin/preview",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AdminOrdersPreviewPublic,
)
def preview_admin_orders_api(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: AdminOrdersCreate,
) -> Any:
    """管理员批量下单结算预览（仅超管），不扣库存不落库"""
    return preview_admin_orders(
        session=session,
        operator=current_user,
        body=body,
    )


@router.get("/me/{order_id}", response_model=OrderPublic)
def read_user_order(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    order_id: uuid.UUID,
) -> Any:
    """查看当前用户的单个订单"""
    db_order = get_user_order(
        session=session,
        order_id=order_id,
        user_id=current_user.id,
    )
    return to_order_public(session=session, orders=[db_order])[0]


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
    db_order = cancel_order(
        session=session,
        db_order=db_order,
        operator_id=current_user.id,
    )
    return to_order_public(session=session, orders=[db_order])[0]


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
    user_id: uuid.UUID | None = None,
) -> Any:
    """查看全部订单，可按用户和状态过滤（仅超级管理员可用）"""
    orders, count = list_orders(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
        user_id=user_id,
    )
    return OrdersPublic(
        data=to_order_public(session=session, orders=orders),
        count=count,
    )


@router.get(
    "/{order_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=OrderPublic,
)
def read_order(*, session: SessionDep, order_id: uuid.UUID) -> Any:
    """查看单个订单（仅超级管理员可用）"""
    db_order = get_order(session=session, order_id=order_id)
    return to_order_public(session=session, orders=[db_order])[0]


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
    db_order = fulfill_order(
        session=session,
        db_order=db_order,
        operator_id=current_user.id,
    )
    return to_order_public(session=session, orders=[db_order])[0]


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
    db_order = cancel_order(
        session=session,
        db_order=db_order,
        operator_id=current_user.id,
    )
    return to_order_public(session=session, orders=[db_order])[0]


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
    db_order = refund_order(
        session=session,
        db_order=db_order,
        operator_id=current_user.id,
    )
    return to_order_public(session=session, orders=[db_order])[0]


@router.post(
    "/{order_id}/sync-status",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=OrderPublic,
)
def sync_order_status_api(
    *,
    session: SessionDep,
    order_id: uuid.UUID,
) -> Any:
    """同步上游订单状态（仅超级管理员可用）"""
    db_order = get_order(session=session, order_id=order_id)
    db_order = sync_order_status(session=session, db_order=db_order)
    return to_order_public(session=session, orders=[db_order])[0]
