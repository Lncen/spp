"""通知渠道：本包只做导出，渠道注册在 registry/loader 中显式完成"""

from app.modules.notification.infrastructure.channels.base import (
    BaseChannel,
    NotificationChannelError,
)
from app.modules.notification.infrastructure.channels.registry import (
    CHANNELS,
    get_channel,
    register_channel,
)

__all__ = [
    "CHANNELS",
    "BaseChannel",
    "NotificationChannelError",
    "get_channel",
    "register_channel",
]
