"""订单相关定时任务"""

import logging
from datetime import UTC, datetime, timedelta

from celery import shared_task
from fastapi import HTTPException
from sqlalchemy import and_, or_, update
from sqlmodel import Session, select

from app.core.db import engine
from app.modules.order.constants import OrderStatus
from app.modules.order.models import Order
from app.modules.order.service.fulfillment_core import (
    FulfillmentUnknownError,
    claim_order,
    fulfill_claimed_order,
)
from app.modules.order.service.notification import notify_order_exception
from app.modules.order.service.status_sync import (
    SYNCABLE_ORDER_STATUSES,
    apply_refund_applications,
    sync_orders_status,
)
from app.modules.product.constants import RedeemType

logger = logging.getLogger(__name__)

# 认领超时时间：超过该时长仍处于处理中视为执行者失联，转人工确认
CLAIM_STALE_MINUTES = 10


def _mark_stale_claim(*, session: Session, db_order: Order, before: datetime) -> bool:
    """认领超时订单标记异常转人工确认，不自动重新下单"""
    result = session.exec(
        update(Order)
        .where(
            Order.id == db_order.id,
            Order.status == OrderStatus.PROCESSING,
            Order.processing_at.is_not(None),
            Order.processing_at < before,
            Order.supplier_order_id.is_(None),
        )
        .values(
            status=OrderStatus.EXCEPTION,
            failed_at=datetime.now(UTC),
        )
    )
    marked = result.rowcount == 1
    session.commit()
    if marked:
        session.refresh(db_order)
        notify_order_exception(db_order=db_order)
    return marked


def _process_candidate(
    *,
    session: Session,
    db_order: Order,
    reclaim_before: datetime,
) -> str:
    """处理单个候选订单，返回结果分类（fulfilled/reclaimed/skipped）"""
    if db_order.status == OrderStatus.PROCESSING:
        if _mark_stale_claim(
            session=session, db_order=db_order, before=reclaim_before
        ):
            return "reclaimed"
        return "skipped"
    if not claim_order(session=session, db_order=db_order):
        return "skipped"  # 已被其他执行者认领
    fulfill_claimed_order(session=session, db_order=db_order)
    return "fulfilled"


@shared_task(ignore_result=False)
def fulfill_paid_orders_periodic() -> dict:
    """批量流水线：扫描→认领→执行→统计，允许放宽至 60 行

    定时将已付款的 API 履约订单向上游下单，单张失败不阻断其他订单；

    先原子认领再执行，慢任务/多实例并发不会重复下单；
    认领超时订单转人工确认，明确失败回滚重试。
    """
    stats = {
        "checked": 0,
        "fulfilled": 0,
        "failed": 0,
        "unknown": 0,
        "reclaimed": 0,
        "errors": [],
    }
    reclaim_before = datetime.now(UTC) - timedelta(minutes=CLAIM_STALE_MINUTES)
    try:
        with Session(engine) as session:
            orders = session.exec(
                select(Order).where(
                    Order.fulfillment_type == RedeemType.AUTO_API,
                    Order.supplier_order_id.is_(None),
                    or_(
                        Order.status == OrderStatus.PAID,
                        and_(
                            Order.status == OrderStatus.PROCESSING,
                            Order.processing_at.is_not(None),
                            Order.processing_at < reclaim_before,
                        ),
                    ),
                )
            ).all()
            stats["checked"] = len(orders)
            for order in orders:
                try:
                    outcome = _process_candidate(
                        session=session,
                        db_order=order,
                        reclaim_before=reclaim_before,
                    )
                    if outcome == "skipped":
                        continue
                    stats[outcome] += 1
                except FulfillmentUnknownError as exc:
                    stats["unknown"] += 1
                    logger.warning("订单 %s 履约结果未知: %s", order.order_no, exc)
                except HTTPException as exc:
                    stats["failed"] += 1
                    logger.warning(
                        "订单 %s 向上游下单失败: %s", order.order_no, exc.detail
                    )
                except Exception as exc:  # noqa: BLE001
                    stats["errors"].append(str(exc))
                    logger.exception("订单 %s 履约异常", order.order_no)
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
