"""通知中心领域层"""

from app.modules.notification.domain.constants import (
    ChannelType,
    DeliveryStatus,
)
from app.modules.notification.domain.rules import (
    NotificationRule,
    RecipientsSpec,
    get_rules_for_event,
    register_builtin_rules,
    register_rule,
)

__all__ = [
    "ChannelType",
    "DeliveryStatus",
    "NotificationRule",
    "RecipientsSpec",
    "get_rules_for_event",
    "register_builtin_rules",
    "register_rule",
]
