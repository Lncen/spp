"""订单模块：履约与状态同步"""

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.order.constants import OrderStatus
from app.modules.order.models import Order
from app.modules.order.service.fulfillment_core import (
    FulfillmentUnknownError,
    claim_order,
    fulfill_claimed_order,
)
from app.modules.order.service.status_sync import sync_orders_status
from app.modules.product.constants import RedeemType
from app.modules.supplier.service.clients.base import SupplierClientError
from app.modules.wallet.service import adjust_balance, get_wallet_by_user_id

logger = logging.getLogger(__name__)


def _refund_order(
    *,
    session: Session,
    db_order: Order,
    amount: Decimal,
    operator_id: Any = None,
) -> None:
    """按指定金额退款入账，只写流水不提交"""
    wallet = get_wallet_by_user_id(session=session, user_id=db_order.user_id)
    if not wallet:
        raise HTTPException(status_code=400, detail="钱包不存在")
    adjust_balance(
        session=session,
        wallet=wallet,
        amount=amount,
        tx_type="refund",
        ref_type="order",
        ref_id=db_order.id,
        remark=f"订单 {db_order.order_no} 退款",
        operator_id=operator_id,
        commit=False,
    )


def cancel_order(
    *,
    session: Session,
    db_order: Order,
    operator_id: uuid.UUID | None = None,  # noqa: ARG001
) -> Order:
    """申请退单：状态置申请售后中，后续由 celery 向上游申请退单"""
    if db_order.status not in (
        OrderStatus.PAID,
        OrderStatus.PENDING,
        OrderStatus.PROCESSING,
    ):
        raise HTTPException(status_code=400, detail="当前状态不可申请退单")
    if not db_order.can_refund:
        raise HTTPException(status_code=400, detail="该订单不支持向供应商申请退单")
    now = datetime.now(UTC)
    db_order.status = OrderStatus.APPLYING_AFTER_SALE
    db_order.canceled_at = now
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order


def refund_order(
    *,
    session: Session,
    db_order: Order,
    amount: Decimal,
    operator_id: uuid.UUID | None = None,
) -> Order:
    """管理员手动退款：仅已完成订单可用，金额由管理员核对且不能超过订单金额"""
    if db_order.status != OrderStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="仅已完成订单可手动退款")
    if amount > db_order.total_amount:
        raise HTTPException(status_code=400, detail="退款金额不能超过订单金额")
    _refund_order(
        session=session,
        db_order=db_order,
        amount=amount,
        operator_id=operator_id,
    )
    db_order.status = OrderStatus.REFUNDED
    db_order.refunded_at = datetime.now(UTC)
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order


def _merge_upstream_statuses(statuses: list[OrderStatus]) -> OrderStatus:
    """多商品项取最不利状态，异常与退单中优先于已完成"""
    priority = {
        OrderStatus.EXCEPTION: 0,
        OrderStatus.REFUNDING: 1,
        OrderStatus.SUPPLEMENTING: 2,
        OrderStatus.PENDING: 3,
        OrderStatus.PROCESSING: 4,
        OrderStatus.PAID: 5,
        OrderStatus.COMPLETED: 6,
        OrderStatus.CANCELED: 7,
        OrderStatus.REFUNDED: 8,
    }
    return min(statuses, key=lambda status: priority[status])


def fulfill_order(
    *,
    session: Session,
    db_order: Order,
    operator_id: uuid.UUID | None = None,  # noqa: ARG001
    fail_limit: int | None = None,
) -> Order:
    """履约订单：先原子认领再执行，防止并发重复履约

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
