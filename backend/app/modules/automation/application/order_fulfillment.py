"""自动化模块：订单履约编排（认领、调用上游、失败分流）

流程编排在本模块；订单状态转换规则在 order.application.order_state，
上游能力调用在 supplier.application.upstream_order。
"""

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


def _query_after_submit(*, session: Session, db_order: Order) -> UpstreamOrder | None:
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
    """执行已认领订单的履约：调用上游并回写结果，失败按结果是否明确分流"""
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
    # _finalize(session=session, db_order=db_order, is_api=is_api, now=now)
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order


def fulfill_order(
    *,
    session: Session,
    db_order: Order,
    fail_limit: int | None = None,
) -> Order:
    """履约订单（同步入口）：先原子认领再执行，防止并发重复履约

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
