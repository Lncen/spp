"""通知中心：Celery 异步投递任务"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from celery import shared_task  # type: ignore[import-untyped]
from sqlmodel import Session

from app.core.db import engine
from app.modules.notification.domain.constants import DeliveryStatus
from app.modules.notification.infrastructure.channels.loader import load_channels
from app.modules.notification.infrastructure.channels.registry import get_channel
from app.modules.notification.models import Notification, NotificationDelivery

logger = logging.getLogger(__name__)


@shared_task(  # type: ignore[untyped-decorator]
    bind=True,
    ignore_result=True,
    name="app.modules.notification.infrastructure.tasks.deliver_notification",
    max_retries=8,
    default_retry_delay=30,
)
def deliver_notification(self: Any, delivery_id: str) -> None:
    """执行一次渠道投递：尝试次数未超限时失败自动重试，超限进入 failed 终态"""
    load_channels()
    with Session(engine) as session:
        delivery = session.get(
            NotificationDelivery, uuid.UUID(delivery_id)
        )
        if delivery is None or delivery.status in {
            DeliveryStatus.SENT,
            DeliveryStatus.CANCELED,
        }:
            return
        notification = session.get(Notification, delivery.notification_id)
        if notification is None:
            delivery.status = DeliveryStatus.CANCELED
            session.add(delivery)
            session.commit()
            return

        delivery.status = DeliveryStatus.SENDING
        delivery.attempt_count += 1
        session.add(delivery)
        session.commit()
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
            return

        delivery.status = DeliveryStatus.SENT
        delivery.sent_at = datetime.now(UTC)
        session.add(delivery)
        session.commit()
