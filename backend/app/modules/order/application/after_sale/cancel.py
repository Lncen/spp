"""订单模块：取消订单"""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import update
from sqlmodel import Session

from app.modules.order.application.after_sale.refund import refund_to_wallet
from app.modules.order.domain.constants import OrderStatus
from app.modules.order.models import Order
from app.modules.order.repositories.stock import restore_stock
from app.modules.product.constants import RedeemType


def _local_cancel_order(
    *,
    session: Session,
    db_order: Order,
    operator_id: uuid.UUID | None,
    now: datetime,
) -> Order:
    """本地取消未向上游下单的订单：全额退款并回补库存，原子防并发履约

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
            (OrderStatus.PAID, OrderStatus.PENDING, OrderStatus.PROCESSING)
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
    """取消订单：未向上游下单的订单本地退款，已向上游下单的 API 订单申请售后"""
    if db_order.status not in (
        OrderStatus.PAID,
        OrderStatus.PENDING,
        OrderStatus.PROCESSING,
    ):
        raise HTTPException(status_code=400, detail="当前状态不可申请退单")
    if not db_order.can_refund:
        raise HTTPException(status_code=400, detail="该订单不支持向供应商申请退单")
    now = datetime.now(UTC)
    is_api = db_order.fulfillment_type == RedeemType.AUTO_API
    if (
        is_api
        and db_order.status == OrderStatus.PROCESSING
        and db_order.supplier_order_id is None
    ):
        # 履约执行中（已认领、上游调用未返回）：直接取消可能重复下单，稍后重试
        raise HTTPException(status_code=400, detail="订单正在履约中，请稍后重试")
    if is_api and db_order.supplier_order_id is not None:
        # 已向上游下单：申请售后中，由 celery 向上游申请退单
        db_order.status = OrderStatus.APPLYING_AFTER_SALE
        db_order.canceled_at = now
        session.add(db_order)
        session.commit()
        session.refresh(db_order)
        return db_order
    return _local_cancel_order(
        session=session,
        db_order=db_order,
        operator_id=operator_id,
        now=now,
    )
