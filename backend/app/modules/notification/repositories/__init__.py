"""通知中心数据访问层"""

from app.modules.notification.repositories.delivery import create_delivery
from app.modules.notification.repositories.notification import (
    count_unread_notifications,
    count_user_notifications,
    create_notification,
    get_user_notification_or_404,
    list_user_notifications,
    mark_all_read,
    mark_notification_read,
)

__all__ = [
    "count_unread_notifications",
    "count_user_notifications",
    "create_delivery",
    "create_notification",
    "get_user_notification_or_404",
    "list_user_notifications",
    "mark_all_read",
    "mark_notification_read",
]
