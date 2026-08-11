"""通知渠道：站内通知（in_app）"""

from sqlmodel import Session

from app.modules.notification.domain.constants import ChannelType
from app.modules.notification.infrastructure.channels.base import BaseChannel
from app.modules.notification.infrastructure.channels.registry import register_channel
from app.modules.notification.models import Notification, NotificationDelivery


@register_channel(ChannelType.IN_APP)
class InAppChannel(BaseChannel):
    """站内通知：通知记录已随事件落库，视为直接送达，无需外部调用"""

    def send(
        self,
        *,
        delivery: NotificationDelivery,
        notification: Notification,
        session: Session,
    ) -> None:
        return None
