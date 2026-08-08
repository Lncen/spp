"""订单相关定时任务"""

import logging

from celery import shared_task
from sqlmodel import Session, select

from app.core.db import engine
from app.modules.order.constants import OrderStatus
from app.modules.order.models import Order
from app.modules.order.service.fulfillment import fulfill_order
from app.modules.order.service.status_sync import (
    SYNCABLE_ORDER_STATUSES,
    apply_refund_applications,
    sync_orders_status,
)
from app.modules.product.constants import RedeemType

logger = logging.getLogger(__name__)


@shared_task(ignore_result=False)
def fulfill_paid_orders_periodic() -> dict:
    """定时将已付款的 API 履约订单向上游下单，单张失败不阻断其他订单

    失败次数在履约服务层累计，达到阈值由服务层标记异常并触发通知。
    """
    stats = {"checked": 0, "fulfilled": 0, "failed": 0, "errors": []}
    try:
        with Session(engine) as session:
            orders = session.exec(
                select(Order).where(
                    Order.status == OrderStatus.PAID,
                    Order.fulfillment_type == RedeemType.AUTO_API,
                    Order.supplier_order_id.is_(None),
                )
            ).all()
            stats["checked"] = len(orders)
            for order in orders:
                try:
                    fulfill_order(session=session, db_order=order)
                    stats["fulfilled"] += 1
                except Exception as exc:  # noqa: BLE001
                    stats["failed"] += 1
                    logger.warning("订单 %s 向上游下单失败: %s", order.order_no, exc)
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append(str(exc))
    return stats


@shared_task(ignore_result=False)
def sync_order_status_periodic() -> dict:
    """定时批量同步上游订单状态（仅处理可同步状态的 API 履约订单）"""
    stats = {"checked": 0, "updated": 0, "unchanged": 0, "errors": []}
    try:
        with Session(engine) as session:
            orders = session.exec(
                select(Order).where(
                    Order.fulfillment_type == RedeemType.AUTO_API,
                    Order.supplier_order_id.is_not(None),
                    Order.status.in_(tuple(SYNCABLE_ORDER_STATUSES)),
                )
            ).all()
            stats["checked"] = len(orders)
            # 处理退单申请
            apply_refund_applications(session=session, db_orders=list(orders))

            # 同步订单状态
            before = {order.id: order.status for order in orders}
            updated = sync_orders_status(
                session=session,
                db_orders=list(orders),
            )
            stats["updated"] = sum(
                1 for order in updated if before.get(order.id) != order.status
            )
            stats["unchanged"] = len(updated) - stats["updated"]
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append(str(exc))
    return stats
