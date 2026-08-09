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
    OrderPublic,
    OrderRefundRequest,
    OrdersPublic,
    OrderStatusUpdateRequest,
    SupplierOrderIdUpdateRequest,
)
from app.modules.order.service import (
    create_admin_orders,
    create_orders,
    preview_admin_orders,
)
from app.modules.order.service.fulfillment import (
    cancel_order,
    fulfill_order,
    record_supplier_order_id,
    refund_order,
    sync_order_status,
    update_order_status,
)
from app.modules.order.service.query import (
    get_order,
    get_user_order,
    list_orders,
    list_user_orders,
    to_order_list_item,
    to_order_public,
)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=AdminOrdersPublic)
def create_user_orders(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: AdminOrdersCreate,
) -> Any:
    """批量创建订单（下单即扣款），逐单独立返回创建状态"""
    return create_orders(session=session, user=current_user, body=body)


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
        data=to_order_list_item(session=session, orders=orders),
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
    param_value: str | None = None,
) -> Any:
    """查看全部订单，可按用户和状态过滤（仅超级管理员可用）"""
    orders, count = list_orders(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
        user_id=user_id,
        param_value=param_value,
    )
    return OrdersPublic(
        data=to_order_list_item(session=session, orders=orders),
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
    body: OrderRefundRequest,
) -> Any:
    """管理员手动退款，按指定金额入账（仅超级管理员可用）"""
    db_order = get_order(session=session, order_id=order_id)
    db_order = refund_order(
        session=session,
        db_order=db_order,
        operator_id=current_user.id,
        amount=body.amount,
    )
    return to_order_public(session=session, orders=[db_order])[0]


@router.post(
    "/{order_id}/status",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=OrderPublic,
)
def update_order_status_api(
    *,
    session: SessionDep,
    order_id: uuid.UUID,
    body: OrderStatusUpdateRequest,
) -> Any:
    """管理员手动设置订单状态（仅超级管理员可用）"""
    db_order = get_order(session=session, order_id=order_id)
    db_order = update_order_status(
        session=session,
        db_order=db_order,
        status=body.status,
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


@router.post(
    "/{order_id}/supplier-order-id",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=OrderPublic,
)
def record_supplier_order_id_api(
    *,
    session: SessionDep,
    order_id: uuid.UUID,
    body: SupplierOrderIdUpdateRequest,
) -> Any:
    """人工确认上游已下单后补录供应商订单号（仅超级管理员）"""
    db_order = get_order(session=session, order_id=order_id)
    db_order = record_supplier_order_id(
        session=session,
        db_order=db_order,
        supplier_order_id=body.supplier_order_id,
    )
    return to_order_public(session=session, orders=[db_order])[0]
