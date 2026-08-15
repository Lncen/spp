"""通知中心：领域常量（渠道、投递状态、接收人角色）"""


class ChannelType:
    """通知渠道类型"""

    IN_APP = "in_app"
    EMAIL = "email"


class DeliveryStatus:
    """投递状态机：pending -> sending -> sent / failed / canceled"""

    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELED = "canceled"


class RecipientRole:
    """内置接收人角色"""

    SUPERUSER = "superuser"


DEFAULT_MAX_ATTEMPTS = 3
MANUAL_EMAIL_TEMPLATE = "notification_manual.html"
