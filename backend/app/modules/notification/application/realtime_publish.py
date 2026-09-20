"""通知中心：通知创建后实时发布（best-effort）

实时通道只是提醒，PostgreSQL 中的 Notification 才是事实来源；
发布失败不影响通知落库，前端可在打开通知中心时重新拉取兜底。
"""

import logging

from app.modules.notification.domain.constants import NotificationRealtimeEvent
from app.modules.notification.models import Notification
from app.modules.realtime.publisher import publish_to_user

logger = logging.getLogger(__name__)


def publish_notification_created(notification: Notification) -> bool:
    """向接收用户实时推送 notification.created（仅站内通知且接收人为用户时）"""
    if notification.user_id is None:
        return False
    payload = {
        "id": str(notification.id),
        "title": notification.title,
        "content": notification.content,
        "event_type": notification.event_type,
        "created_at": (
            notification.created_at.isoformat()
            if notification.created_at is not None
            else None
        ),
    }
    return publish_to_user(
        notification.user_id,
        NotificationRealtimeEvent.CREATED,
        payload,
    )
