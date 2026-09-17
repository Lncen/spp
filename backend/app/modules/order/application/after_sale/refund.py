"""订单模块：退款应用服务"""

import logging
import uuid
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session

from app.core.time import get_datetime_cn
from app.modules.order.domain.constants import OrderStatus
from app.modules.order.domain.refund import calc_refund_amount
from app.modules.order.models import Order
from app.modules.order.repositories.stock import restore_stock
from app.modules.wallet.application.wallet_adjust import adjust_balance
from app.modules.wallet.application.wallet_query import get_or_create_user_wallet

logger = logging.getLogger(__name__)


def refund_to_wallet(
    *,
    session: Session,
    db_order: Order,
    amount: Decimal,
    operator_id: uuid.UUID | None = None,
) -> None:
    """按指定金额退款入账，只写流水不提交"""
    wallet = get_or_create_user_wallet(session=session, user_id=db_order.user_id)
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


def refund_order(
    *,
    session: Session,
    db_order: Order,
    amount: Decimal,
    operator_id: uuid.UUID | None = None,
    remark: str | None = None,
) -> Order:
    """管理员手动退款：仅已完成订单可用，金额由管理员核对且不能超过订单金额"""
    if db_order.status != OrderStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="仅已完成订单可手动退款")
    if amount > db_order.total_amount:
        raise HTTPException(status_code=400, detail="退款金额不能超过订单金额")
    refund_to_wallet(
        session=session,
        db_order=db_order,
        amount=amount,
        operator_id=operator_id,
    )
    db_order.status = OrderStatus.REFUNDED
    db_order.refunded_at = get_datetime_cn()
    db_order.refunded_amount = amount
    if remark is not None:
        db_order.remark = remark
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order


def auto_refund_order(
    *, session: Session, db_order: Order, upstream_status: OrderStatus
) -> bool:
    """上游已退单/已退款时按公式自动退款入账，非已完成订单回补库存"""
    if db_order.refunded_at is not None or db_order.status == OrderStatus.REFUNDED:
        return False
    amount = calc_refund_amount(db_order=db_order)
    if amount > Decimal("0"):
        wallet = get_or_create_user_wallet(session=session, user_id=db_order.user_id)
        adjust_balance(
            session=session,
            wallet=wallet,
            amount=amount,
            tx_type="refund",
            ref_type="order",
            ref_id=db_order.id,
            remark=f"订单 {db_order.order_no} 上游退单自动退款",
            operator_id=None,
            commit=False,
        )
    if db_order.status != OrderStatus.COMPLETED:
        restore_stock(
            session=session,
            product_id=db_order.product_id,
            quantity=db_order.quantity,
        )
    db_order.refunded_amount = amount
    db_order.status = OrderStatus.REFUNDED
    db_order.refunded_at = get_datetime_cn()
    if upstream_status == OrderStatus.CANCELED:
        db_order.canceled_at = get_datetime_cn()
    session.add(db_order)
    return True
