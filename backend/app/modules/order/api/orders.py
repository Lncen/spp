"""订单模块：路由层"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import (
    CurrentUser,
    SessionDep,
    require_any_permission,
    require_permission,
)
from app.modules.order.application.after_sale.cancel import cancel_order
from app.modules.order.application.after_sale.refund import refund_order
from app.modules.order.application.create import (
    create_admin_orders,
    create_orders,
    preview_orders,
)
from app.modules.order.application.fulfillment import (
    fulfill_order,
    record_supplier_order_id,
    sync_order_status,
    update_order_status,
)
from app.modules.order.application.query import (
    get_order,
    get_user_order,
    list_orders,
    list_user_orders,
    to_order_list_item,
    to_order_public,
)
from app.modules.order.domain.constants import OrderStatus
from app.modules.order.schemas import (
    AdminOrdersCreate,
    AdminOrdersPreviewPublic,
    AdminOrdersPublic,
    OrderPublic,
    OrderRefundRequest,
    OrderRemarkRequest,
    OrdersPublic,
    OrderStatusUpdateRequest,
    SupplierOrderIdUpdateRequest,
)
from app.modules.system_log.application.audit_log_create import record_audit_log

router = APIRouter(prefix="/orders", tags=["orders"])


def _request_meta(request: Request) -> tuple[str | None, str | None, str | None]:
    """从 HTTP 请求中提取审计所需的 ip / user_agent / request_id"""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    request_id = request.headers.get("x-request-id")
    return ip, user_agent, request_id


@router.post(
    "/",
    dependencies=[
        Depends(require_any_permission("order:create", detail="暂无下单权限"))
    ],
    response_model=AdminOrdersPublic,
)
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
    dependencies=[Depends(require_permission("order:admin_create"))],
    response_model=AdminOrdersPublic,
)
def create_admin_orders_api(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: AdminOrdersCreate,
) -> Any:
    """管理员批量下单，跳过钱包与余额校验"""
    return create_admin_orders(
        session=session,
        operator=current_user,
        body=body,
    )


@router.post(
    "/admin/preview",
    dependencies=[Depends(require_permission("order:admin_create"))],
    response_model=AdminOrdersPreviewPublic,
)
def preview_admin_orders_api(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: AdminOrdersCreate,
) -> Any:
    """管理员批量下单结算预览，不扣库存不落库"""
    return preview_orders(
        session=session,
        operator=current_user,
        body=body,
    )


@router.post(
    "/preview",
    dependencies=[
        Depends(require_any_permission("order:create", detail="暂无下单权限"))
    ],
    response_model=AdminOrdersPreviewPublic,
)
def preview_user_orders_api(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    body: AdminOrdersCreate,
) -> Any:
    """组合下单结算预览：按当前用户等级计价，不扣库存不落库"""
    return preview_orders(
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
    dependencies=[Depends(require_permission("order:view"))],
    response_model=OrdersPublic,
)
def read_orders(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    status: OrderStatus | None = None,
    user_id: uuid.UUID | None = None,
    keyword: str | None = None,
) -> Any:
    """查看全部订单，可按用户、状态与关键字过滤"""
    orders, count = list_orders(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
        user_id=user_id,
        keyword=keyword,
    )
    return OrdersPublic(
        data=to_order_list_item(session=session, orders=orders),
        count=count,
    )


@router.get(
    "/{order_id}",
    dependencies=[Depends(require_permission("order:view"))],
    response_model=OrderPublic,
)
def read_order(*, session: SessionDep, order_id: uuid.UUID) -> Any:
    """查看单个订单"""
    db_order = get_order(session=session, order_id=order_id)
    return to_order_public(session=session, orders=[db_order])[0]


@router.post(
    "/{order_id}/fulfill",
    dependencies=[Depends(require_permission("order:fulfill"))],
    response_model=OrderPublic,
)
def fulfill_order_api(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    order_id: uuid.UUID,
    body: OrderRemarkRequest | None = None,
) -> Any:
    """履约订单"""
    db_order = get_order(session=session, order_id=order_id)
    db_order = fulfill_order(
        session=session,
        db_order=db_order,
        operator_id=current_user.id,
        remark=body.remark if body else None,
    )
    return to_order_public(session=session, orders=[db_order])[0]


@router.post(
    "/{order_id}/cancel",
    dependencies=[Depends(require_permission("order:cancel"))],
    response_model=OrderPublic,
)
def cancel_order_api(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    order_id: uuid.UUID,
    body: OrderRemarkRequest | None = None,
) -> Any:
    """管理员取消待处理订单"""
    db_order = get_order(session=session, order_id=order_id)
    old_status = db_order.status
    db_order = cancel_order(
        session=session,
        db_order=db_order,
        operator_id=current_user.id,
        remark=body.remark if body else None,
    )
    ip, user_agent, request_id = _request_meta(request)
    record_audit_log(
        session=session,
        actor=current_user,
        action="order.cancel",
        resource_type="order",
        resource_id=db_order.order_no,
        before={"status": old_status},
        after={"status": db_order.status},
        changes={"status": {"old": old_status, "new": db_order.status}},
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
    )
    return to_order_public(session=session, orders=[db_order])[0]


@router.post(
    "/{order_id}/refund",
    dependencies=[Depends(require_permission("order:refund"))],
    response_model=OrderPublic,
)
def refund_order_api(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    order_id: uuid.UUID,
    body: OrderRefundRequest,
) -> Any:
    """管理员手动退款，按指定金额入账"""
    db_order = get_order(session=session, order_id=order_id)
    old_status = db_order.status
    refund_amount = str(body.amount)
    db_order = refund_order(
        session=session,
        db_order=db_order,
        operator_id=current_user.id,
        amount=body.amount,
        remark=body.remark,
    )
    ip, user_agent, request_id = _request_meta(request)
    record_audit_log(
        session=session,
        actor=current_user,
        action="order.refund",
        resource_type="order",
        resource_id=db_order.order_no,
        before={"status": old_status, "refund_amount": None},
        after={"status": db_order.status, "refund_amount": refund_amount},
        changes={
            "status": {"old": old_status, "new": db_order.status},
            "refund_amount": {"old": None, "new": refund_amount},
        },
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
    )
    return to_order_public(session=session, orders=[db_order])[0]


@router.post(
    "/{order_id}/status",
    dependencies=[Depends(require_permission("order:update"))],
    response_model=OrderPublic,
)
def update_order_status_api(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    order_id: uuid.UUID,
    body: OrderStatusUpdateRequest,
) -> Any:
    """管理员手动设置订单状态"""
    db_order = get_order(session=session, order_id=order_id)
    old_status = db_order.status
    db_order = update_order_status(
        session=session,
        db_order=db_order,
        status=body.status,
    )
    ip, user_agent, request_id = _request_meta(request)
    record_audit_log(
        session=session,
        actor=current_user,
        action="order.update_status",
        resource_type="order",
        resource_id=db_order.order_no,
        before={"status": old_status},
        after={"status": db_order.status},
        changes={"status": {"old": old_status, "new": db_order.status}},
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
    )
    return to_order_public(session=session, orders=[db_order])[0]


@router.post(
    "/{order_id}/sync-status",
    dependencies=[Depends(require_permission("order:update"))],
    response_model=OrderPublic,
)
def sync_order_status_api(
    *,
    session: SessionDep,
    order_id: uuid.UUID,
) -> Any:
    """同步上游订单状态"""
    db_order = get_order(session=session, order_id=order_id)
    db_order = sync_order_status(session=session, db_order=db_order)
    return to_order_public(session=session, orders=[db_order])[0]


@router.post(
    "/{order_id}/supplier-order-id",
    dependencies=[Depends(require_permission("order:update"))],
    response_model=OrderPublic,
)
def record_supplier_order_id_api(
    *,
    session: SessionDep,
    order_id: uuid.UUID,
    body: SupplierOrderIdUpdateRequest,
) -> Any:
    """人工确认上游已下单后补录供应商订单号"""
    db_order = get_order(session=session, order_id=order_id)
    db_order = record_supplier_order_id(
        session=session,
        db_order=db_order,
        supplier_order_id=body.supplier_order_id,
    )
    return to_order_public(session=session, orders=[db_order])[0]
