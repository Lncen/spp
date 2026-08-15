"""通知中心数据访问层"""

from app.modules.notification.repositories.delivery import (
    claim_delivery_for_sending,
    create_delivery,
    get_delivery_or_404,
    recover_stale_deliveries,
    reset_delivery_for_retry,
)
from app.modules.notification.repositories.notification import (
    count_admin_deliveries,
    count_unread_notifications,
    count_user_notifications,
    create_notification,
    get_notifications_by_ids,
    get_user_notification_or_404,
    list_admin_deliveries,
    list_user_notifications,
    mark_all_read,
    mark_notification_read,
)

__all__ = [
    "claim_delivery_for_sending",
    "count_admin_deliveries",
    "count_unread_notifications",
    "count_user_notifications",
    "create_delivery",
    "create_notification",
    "get_delivery_or_404",
    "get_notifications_by_ids",
    "get_user_notification_or_404",
    "list_admin_deliveries",
    "list_user_notifications",
    "mark_all_read",
    "mark_notification_read",
    "recover_stale_deliveries",
    "reset_delivery_for_retry",
]
