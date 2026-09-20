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


class ConsumptionStatus:
    """事件消费状态机：pending -> processing -> done / failed"""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class RecipientRole:
    """内置接收人角色"""

    SUPERUSER = "superuser"


class NotificationRealtimeEvent:
    """通知模块对客户端发布的实时事件名（经 realtime.publisher 发送）"""

    CREATED = "notification.created"


def build_dedupe_key(
    *,
    event_id: object,
    rule_key: str,
    recipient: str,
) -> str:
    """事件触发的通知幂等键：同一事件 + 同一规则 + 同一接收人只生成一条通知"""
    return f"{event_id}:{rule_key}:{recipient}"


DEFAULT_MAX_ATTEMPTS = 3
MANUAL_EMAIL_TEMPLATE = "notification_manual.html"

# 事件消费重试：失败后指数退避重试，超过次数上限后不再自动重试
CONSUMPTION_MAX_ATTEMPTS = 5
CONSUMPTION_BASE_RETRY_SECONDS = 60
CONSUMPTION_MAX_RETRY_SECONDS = 3600
# processing 超过该时长视为 worker 中断，可被重试任务重新认领
CONSUMPTION_STALE_MINUTES = 15
