"""订单模块：履约与状态管理（编排 + 手动接口）

流程编排在本模块；订单状态转换规则在 order.application.order_state，
上游能力调用在 supplier.application.upstream_order。
automation 仅通过执行器 / 定时任务触发本模块编排。
"""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlmodel import Session

from app.core.config import settings
from app.modules.order.application.order_state import (
    claim_order,
    finalize_fulfillment,
    mark_unknown_outcome,
    record_upstream_order_created,
    resolve_fulfill_target,
    rollback_claim_on_failure,
    to_order_status,
)
from app.modules.order.application.sync import sync_orders_status
from app.modules.order.domain.constants import OrderStatus
from app.modules.order.models import Order
from app.modules.product.constants import RedeemType
from app.modules.supplier.application.upstream_order import (
    normalize_upstream_id,
    query_upstream_orders_status,
    submit_upstream_order,
)
from app.modules.supplier.infrastructure.clients.base import (
    SupplierClientError,
    SupplierClientUnknownError,
)
from app.modules.supplier.schemas.upstream import UpstreamOrder


class FulfillmentUnknownError(Exception):
    """履约结果未知（上游可能已下单），已转人工确认，不应自动重试"""


def _create_upstream_order(
    *,
    session: Session,
    db_order: Order,
    is_api: bool,
    now: datetime,
    fail_limit: int,
) -> None:
    """调用上游下单，失败按结果是否明确分流（均抛异常终止）"""
    if not is_api:
        return
    try:
        supplier_id, sku_id = resolve_fulfill_target(
            session=session, db_order=db_order
        )
        upstream_params = dict(db_order.params or {})
        upstream_params.pop("customer_order_id", None)
        supplier_order_id = submit_upstream_order(
            session=session,
            supplier_id=supplier_id,
            sku_id=sku_id,
            quantity=db_order.quantity,
            params=upstream_params,
            customer_order_id=db_order.order_no,
        )
        record_upstream_order_created(
            db_order=db_order, supplier_order_id=supplier_order_id
        )
        session.add(db_order)
    except SupplierClientUnknownError as exc:
        mark_unknown_outcome(session=session, db_order=db_order)
        raise FulfillmentUnknownError(
            f"供应商履约结果未知，订单已转人工确认: {exc}"
        ) from exc
    except SupplierClientError as exc:
        rollback_claim_on_failure(
            session=session,
            db_order=db_order,
            now=now,
            fail_limit=fail_limit,
        )
        raise HTTPException(
            status_code=502,
            detail=f"供应商履约失败: {exc}",
        ) from exc


def _query_after_submit(
    *, session: Session, db_order: Order
) -> UpstreamOrder | None:
    """下单成功后查询上游初始状态；查询失败返回 None（保持 PENDING）"""
    try:
        supplier_id = resolve_fulfill_target(
            session=session, db_order=db_order
        )[0]
        assert db_order.supplier_order_id is not None
        statuses = query_upstream_orders_status(
            session=session,
            supplier_id=supplier_id,
            upstream_order_ids=[db_order.supplier_order_id],
        )
    except SupplierClientError:
        return None
    return statuses.get(normalize_upstream_id(db_order.supplier_order_id))


def _finalize(
    *, session: Session, db_order: Order, is_api: bool, now: datetime
) -> None:
    """上游下单成功后回写最终状态（不提交）"""
    upstream_status = None
    if is_api:
        upstream = _query_after_submit(session=session, db_order=db_order)
        if upstream is not None:
            upstream_status = to_order_status(
                db_order.supplier_order_id, upstream.status
            )
    finalize_fulfillment(
        db_order=db_order,
        is_api=is_api,
        now=now,
        upstream_status=upstream_status,
    )


def fulfill_claimed_order(
    *,
    session: Session,
    db_order: Order,
    fail_limit: int | None = None,
) -> Order:
    """执行已认领订单的履约：调用上游并回写结果，失败按结果是否明确分流

    API 订单下单成功即保持 PROCESSING（record_upstream_order_created 已置位），
    不再立即查询上游状态，后续状态由 sync_order_status_periodic 定时同步；
    非 API 订单按原逻辑直接回写终态。
    """
    is_api = db_order.fulfillment_type == RedeemType.AUTO_API
    now = datetime.now(UTC)
    if fail_limit is None:
        fail_limit = settings.ORDER_FULFILL_FAIL_LIMIT

    _create_upstream_order(
        session=session,
        db_order=db_order,
        is_api=is_api,
        now=now,
        fail_limit=fail_limit,
    )
    db_order.fulfill_failed_count = 0  # 上游下单成功，清零失败计数
    if not is_api:
        _finalize(session=session, db_order=db_order, is_api=is_api, now=now)
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order


def fulfill_order(
    *,
    session: Session,
    db_order: Order,
    operator_id: uuid.UUID | None = None,  # noqa: ARG001
    fail_limit: int | None = None,
) -> Order:
    """履约订单（同步）：先原子认领再执行，防止并发重复履约

    明确失败回滚重试；结果未知（超时/断连）转人工确认。
    """
    if not claim_order(session=session, db_order=db_order):
        raise HTTPException(status_code=400, detail="当前状态不可履约")
    try:
        return fulfill_claimed_order(
            session=session, db_order=db_order, fail_limit=fail_limit
        )
    except FulfillmentUnknownError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def record_supplier_order_id(
    *,
    session: Session,
    db_order: Order,
    supplier_order_id: str,
) -> Order:
    """人工确认上游已下单后补录供应商订单号，恢复正常履约流程"""
    supplier_order_id = supplier_order_id.strip()
    if not supplier_order_id:
        raise HTTPException(status_code=422, detail="供应商订单号不能为空")
    db_order.supplier_order_id = supplier_order_id
    if db_order.status in (OrderStatus.PAID, OrderStatus.EXCEPTION):
        db_order.status = OrderStatus.PENDING
        db_order.fulfill_failed_count = 0
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order


def sync_order_status(*, session: Session, db_order: Order) -> Order:
    """查询上游订单状态并刷新本地状态快照（终态订单跳过）"""
    if db_order.fulfillment_type != RedeemType.AUTO_API:
        raise HTTPException(status_code=400, detail="订单不包含 API 履约商品")
    if not db_order.supplier_order_id:
        raise HTTPException(
            status_code=400,
            detail=f"商品 {db_order.product_name} 缺少供应商订单号",
        )
    try:
        updated = sync_orders_status(session=session, db_orders=[db_order])
    except SupplierClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return updated[0] if updated else db_order


def update_order_status(
    *,
    session: Session,
    db_order: Order,
    status: OrderStatus,
) -> Order:
    """管理员手动设置订单状态，异常订单可恢复为已付款"""
    allowed_statuses = (
        OrderStatus.PROCESSING,
        OrderStatus.REFUNDING,
        OrderStatus.COMPLETED,
        OrderStatus.EXCEPTION,
        OrderStatus.PAID,
    )
    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="当前状态不允许手动设置")
    if status == OrderStatus.PAID and db_order.status != OrderStatus.EXCEPTION:
        raise HTTPException(status_code=400, detail="仅异常订单可恢复为已付款")
    now = datetime.now(UTC)
    db_order.status = status
    if status == OrderStatus.PROCESSING:
        db_order.processing_at = now
    elif status == OrderStatus.COMPLETED:
        db_order.completed_at = now
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order
