"""订单模块：取消订单"""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import update
from sqlmodel import Session

from app.core.event_bus import create_event_in_session, dispatch_event
from app.modules.automation.models import AutomationEvent
from app.modules.order.application.after_sale.refund import refund_to_wallet
from app.modules.order.domain.constants import OrderStatus
from app.modules.order.models import Order
from app.modules.order.repositories.stock import restore_stock
from app.modules.product.constants import RedeemType

logger = logging.getLogger(__name__)

# 已向上游下单的订单申请售后后发布的事件类型
AFTER_SALE_EVENT_TYPE = "order.after_sale_applied"


def _queue_after_sale_event(*, session: Session, db_order: Order) -> AutomationEvent:
    """在订单事务内登记 order.after_sale_applied 事件，随订单一起提交，避免事件丢失"""
    return create_event_in_session(
        session=session,
        event_type=AFTER_SALE_EVENT_TYPE,
        payload={"order_id": str(db_order.id)},
    )


def _dispatch_after_sale_event(event: AutomationEvent) -> None:
    """订单状态提交后分发售后事件；失败仅记录日志，事件已在库中可追溯补发"""
    try:
        dispatch_event(event)
    except Exception:  # noqa: BLE001
        logger.exception(
            "%s 事件分发失败 event_id=%s", AFTER_SALE_EVENT_TYPE, event.id
        )


def _local_cancel_order(
    *,
    session: Session,
    db_order: Order,
    operator_id: uuid.UUID | None,
    now: datetime,
) -> Order:
    """本地取消订单：全额退款并回补库存，原子防并发履约

    顺序执行的简单流水线（退款、回补库存与条件更新），按 AGENTS.md 放宽至 60 行。
    """
    refund_to_wallet(
        session=session,
        db_order=db_order,
        amount=db_order.total_amount,
        operator_id=operator_id,
    )
    restore_stock(
        session=session,
        product_id=db_order.product_id,
        quantity=db_order.quantity,
    )
    conditions = [
        Order.id == db_order.id,
        Order.status.in_(
            (
                OrderStatus.PAID,
                OrderStatus.PENDING,
                OrderStatus.PROCESSING,
                OrderStatus.EXCEPTION,
            )
        ),
    ]
    if db_order.fulfillment_type == RedeemType.AUTO_API:
        conditions.append(Order.supplier_order_id.is_(None))
    result = session.exec(
        update(Order)
        .where(*conditions)
        .values(
            status=OrderStatus.REFUNDED,
            refunded_at=now,
            canceled_at=now,
            refunded_amount=db_order.total_amount,
        )
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=400, detail="当前状态不可取消")
    session.commit()
    session.refresh(db_order)
    return db_order


def cancel_order(
    *,
    session: Session,
    db_order: Order,
    operator_id: uuid.UUID | None = None,
) -> Order:
    """退单：本地/自动/手动商品直接本地退款，API 商品按是否已上游下单分流"""
    if db_order.status not in (
        OrderStatus.PAID,
        OrderStatus.PENDING,
        OrderStatus.PROCESSING,
        OrderStatus.EXCEPTION,
    ):
        raise HTTPException(status_code=400, detail="当前状态不可申请退单")
    now = datetime.now(UTC)
    is_api = db_order.fulfillment_type == RedeemType.AUTO_API
    if is_api:
        # can_refund 约束的是能否向供应商申请退单，仅对 API 商品生效
        if not db_order.can_refund:
            raise HTTPException(
                status_code=400, detail="该订单不支持向供应商申请退单"
            )
        if (
            db_order.status == OrderStatus.PROCESSING
            and db_order.supplier_order_id is None
        ):
            # 履约执行中（已认领、上游调用未返回）：直接取消可能重复下单，稍后重试
            raise HTTPException(status_code=400, detail="订单正在履约中，请稍后重试")
        if db_order.supplier_order_id is not None:
            # 已向上游下单：申请售后中，由 automation 事件触发上游退单申请
            db_order.status = OrderStatus.APPLYING_AFTER_SALE
            db_order.canceled_at = now
            session.add(db_order)
            event = _queue_after_sale_event(session=session, db_order=db_order)
            session.commit()
            session.refresh(db_order)
            _dispatch_after_sale_event(event)
            return db_order
    return _local_cancel_order(
        session=session,
        db_order=db_order,
        operator_id=operator_id,
        now=now,
    )
