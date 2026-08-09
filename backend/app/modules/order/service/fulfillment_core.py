"""订单履约执行核心：认领、调用上游、失败分流"""

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import update
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.order.constants import OrderStatus
from app.modules.order.models import Order
from app.modules.order.service.notification import notify_order_exception
from app.modules.order.service.status_sync import _query_api_orders_status
from app.modules.product.constants import RedeemType
from app.modules.product.product.models import ProductSupplier
from app.modules.supplier.models import Supplier
from app.modules.supplier.service.clients.base import (
    SupplierClientBase,
    SupplierClientError,
    SupplierClientUnknownError,
)


class FulfillmentUnknownError(Exception):
    """履约结果未知（上游可能已下单），已转人工确认，不应自动重试"""


def _extract_supplier_order_id(result: dict[str, Any]) -> str | None:
    """从上游下单返回中提取供应商订单号"""
    payload = result.get("data") if isinstance(result.get("data"), dict) else result
    for key in ("order_id", "orderId", "id"):
        value = payload.get(key)
        if value is not None:
            return str(value)
    return None


def _fulfill_api_item(*, session: Session, db_order: Order) -> None:
    """调用供应商 API 下单，写入供应商订单号"""
    supplier_id, sku_id = db_order.supplier_id, db_order.sku_id
    if supplier_id is None or not sku_id:
        # 旧订单未落货源快照时回退查询商品当前货源
        supplier_sku = session.exec(
            select(ProductSupplier).where(
                ProductSupplier.product_id == db_order.product_id
            )
        ).first()
        if (
            supplier_sku is None
            or supplier_sku.supplier_id is None
            or not supplier_sku.sku_id
        ):
            raise SupplierClientError("商品未配置供应商或 SKU")
        supplier_id, sku_id = supplier_sku.supplier_id, supplier_sku.sku_id
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise SupplierClientError("供应商不存在")
    client = SupplierClientBase.get_client(supplier)
    try:
        upstream_params = dict(db_order.params or {})
        upstream_params.pop("customer_order_id", None)
        result = client.create_order(
            product_id=sku_id,
            quantity=db_order.quantity,
            customer_order_id=db_order.order_no,
            **upstream_params,
        )
        db_order.supplier_order_id = _extract_supplier_order_id(result)
        db_order.status = OrderStatus.PENDING
        session.add(db_order)
    finally:
        client.close()


def claim_order(*, session: Session, db_order: Order) -> bool:
    """原子认领订单（PAID → PROCESSING），防止并发重复履约"""
    now = datetime.now(UTC)
    result = session.exec(
        update(Order)
        .where(
            Order.id == db_order.id,
            Order.status == OrderStatus.PAID,
            Order.supplier_order_id.is_(None),
        )
        .values(status=OrderStatus.PROCESSING, processing_at=now)
    )
    claimed = result.rowcount == 1
    session.commit()
    if claimed:
        session.refresh(db_order)
    return claimed


def _rollback_claim_on_failure(
    *,
    session: Session,
    db_order: Order,
    now: datetime,
    fail_limit: int,
) -> None:
    """明确失败：回滚认领为已付款，累计失败次数，达阈值标记异常"""
    db_order.status = OrderStatus.PAID
    db_order.fulfill_failed_count = (db_order.fulfill_failed_count or 0) + 1
    if db_order.fulfill_failed_count >= fail_limit:
        db_order.status = OrderStatus.EXCEPTION
        db_order.failed_at = now
        note = f"履约连续失败 {db_order.fulfill_failed_count} 次，已标记异常"
        db_order.remark = (
            f"{db_order.remark}；{note}"[:255] if db_order.remark else note
        )
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    if db_order.status == OrderStatus.EXCEPTION:
        notify_order_exception(db_order=db_order)


def _mark_unknown_outcome(*, session: Session, db_order: Order) -> None:
    """结果未知：标记异常转人工确认，不自动重试"""
    db_order.status = OrderStatus.EXCEPTION
    db_order.failed_at = datetime.now(UTC)
    note = "履约结果未知，需人工确认上游是否已下单"
    db_order.remark = (
        f"{db_order.remark}；{note}"[:255] if db_order.remark else note
    )
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    notify_order_exception(db_order=db_order)


def _finalize_fulfillment(
    *,
    session: Session,
    db_order: Order,
    is_api: bool,
    now: datetime,
) -> None:
    """上游下单成功后回写最终状态（不提交）"""
    if db_order.fulfillment_type == RedeemType.MANUAL:
        db_order.status = OrderStatus.PROCESSING
    elif not is_api:
        db_order.status = OrderStatus.COMPLETED
        db_order.completed_at = now
    else:
        try:
            status = _query_api_orders_status(
                session=session, db_orders=[db_order]
            )[db_order.id]
            db_order.status = status
            if status == OrderStatus.COMPLETED:
                db_order.completed_at = now
        except SupplierClientError:
            # 上游订单已创建，状态查询失败保持 PENDING，由状态同步任务后续处理
            db_order.status = OrderStatus.PENDING


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
        _fulfill_api_item(session=session, db_order=db_order)
    except SupplierClientUnknownError as exc:
        _mark_unknown_outcome(session=session, db_order=db_order)
        raise FulfillmentUnknownError(
            f"供应商履约结果未知，订单已转人工确认: {exc}"
        ) from exc
    except SupplierClientError as exc:
        _rollback_claim_on_failure(
            session=session,
            db_order=db_order,
            now=now,
            fail_limit=fail_limit,
        )
        raise HTTPException(
            status_code=502,
            detail=f"供应商履约失败: {exc}",
        ) from exc


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
    _finalize_fulfillment(
        session=session,
        db_order=db_order,
        is_api=is_api,
        now=now,
    )
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order
