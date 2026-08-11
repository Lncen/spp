"""通知中心数据模型"""

from app.modules.notification.models.delivery import NotificationDelivery
from app.modules.notification.models.notification import Notification

__all__ = ["Notification", "NotificationDelivery"]
