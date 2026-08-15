"""自动化模块：通知中心 Celery 异步投递与兜底扫描任务"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from celery import shared_task  # type: ignore[import-untyped]
from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.modules.notification.domain.constants import (
    DEFAULT_MAX_ATTEMPTS,
    DeliveryStatus,
)
from app.modules.notification.infrastructure.channels.loader import load_channels
from app.modules.notification.infrastructure.channels.registry import get_channel
from app.modules.notification.models import Notification
from app.modules.notification.repositories.delivery import (
    claim_delivery_for_sending,
    recover_stale_deliveries,
)

logger = logging.getLogger(__name__)


@shared_task(  # type: ignore[untyped-decorator]
    bind=True,
    ignore_result=True,
    name="app.modules.automation.infrastructure.tasks.deliver_notification",
    # Celery 层重试上限与投递记录默认最大尝试次数对齐（首次执行不算重试）；
    # 实际重试次数以投递记录 max_attempts 状态机为准
    max_retries=DEFAULT_MAX_ATTEMPTS - 1,
    default_retry_delay=30,
)
def deliver_notification(self: Any, delivery_id: str) -> None:
    """执行一次渠道投递：尝试次数未超限时失败自动重试，超限进入 failed 终态"""
    load_channels()
    with Session(engine) as session:
        # 幂等认领：pending/failed 才可进入 sending，并发重投/兜底重入队时
        # 只有一方能认领成功，防止重复发送
        delivery = claim_delivery_for_sending(
            session=session,
            delivery_id=uuid.UUID(delivery_id),
        )
        if delivery is None:
            return
        notification = session.get(Notification, delivery.notification_id)
        if notification is None:
            delivery.status = DeliveryStatus.CANCELED
            session.add(delivery)
            session.commit()
            return

        try:
            channel = get_channel(delivery.channel)
            channel.send(
                delivery=delivery,
                notification=notification,
                session=session,
            )
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            session.refresh(delivery)
            delivery.status = DeliveryStatus.FAILED
            delivery.error_message = str(exc)[:1000]
            session.add(delivery)
            session.commit()
            if delivery.attempt_count < delivery.max_attempts:
                raise self.retry(exc=exc)
            logger.warning(
                "通知投递失败已达上限: delivery_id=%s channel=%s error=%s",
                delivery.id,
                delivery.channel,
                exc,
            )
            # 终态失败仍向上抛出，便于 Celery 监控（Flower 等）可见失败
            raise exc

        delivery.status = DeliveryStatus.SENT
        delivery.sent_at = datetime.now(UTC)
        session.add(delivery)
        session.commit()


def enqueue_delivery(delivery_id: str) -> bool:
    """将投递任务写入队列；失败不抛出。

    投递记录已在业务事务中落库（唯一事实源），入队失败仅记日志，
    记录保持 pending，由兜底扫描任务保证最终补投，接口不受 broker 抖动影响。
    """
    try:
        deliver_notification.delay(delivery_id)
        return True
    except Exception:  # noqa: BLE001
        logger.exception(
            "通知投递入队失败，等待兜底扫描补投: delivery_id=%s", delivery_id
        )
        return False


@shared_task(  # type: ignore[untyped-decorator]
    ignore_result=True,
    name=(
        "app.modules.automation.infrastructure.tasks."
        "requeue_stale_notification_deliveries"
    ),
)
def requeue_stale_notification_deliveries() -> int:
    """兜底扫描：恢复超时未推进的投递记录并重新入队，防止消息丢失导致永不发送"""
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=settings.NOTIFICATION_STALE_MINUTES)
    with Session(engine) as session:
        stale_ids = recover_stale_deliveries(
            session=session,
            before=cutoff,
            now=now,
        )
    for delivery_id in stale_ids:
        deliver_notification.delay(str(delivery_id))
    if stale_ids:
        logger.info("通知兜底扫描恢复 %d 条投递并重新入队", len(stale_ids))
    return len(stale_ids)
