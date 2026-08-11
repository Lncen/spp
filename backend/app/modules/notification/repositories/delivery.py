"""通知中心：渠道投递记录数据访问"""

import uuid

from sqlmodel import Session

from app.modules.notification.domain.constants import (
    DEFAULT_MAX_ATTEMPTS,
    DeliveryStatus,
)
from app.modules.notification.models import NotificationDelivery


def create_delivery(
    *,
    session: Session,
    notification_id: uuid.UUID,
    channel: str,
) -> NotificationDelivery:
    """创建投递记录并加入会话（不提交，由调用方控制事务）"""
    delivery = NotificationDelivery(
        notification_id=notification_id,
        channel=channel,
        status=DeliveryStatus.PENDING,
        attempt_count=0,
        max_attempts=DEFAULT_MAX_ATTEMPTS,
    )
    session.add(delivery)
    return delivery
