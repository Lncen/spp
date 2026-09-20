"""系统日志领域常量"""

from enum import StrEnum


class LogLevel(StrEnum):
    """系统日志级别"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class SystemLogStatus(StrEnum):
    """系统日志结果状态"""

    SUCCESS = "success"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ActorType(StrEnum):
    """系统日志操作者类型"""

    SYSTEM = "system"
    USER = "user"
    AUTOMATION = "automation"


# 事件载荷中常见的业务资源键，按优先级匹配目标对象
RESOURCE_KEY_MAP: dict[str, str] = {
    "order_id": "order",
    "order_no": "order",
    "product_id": "product",
    "sku_id": "product",
    "supplier_id": "supplier",
    "vendor_id": "supplier",
    "user_id": "user",
    "wallet_id": "wallet",
    "task_id": "automation_task",
    "event_id": "automation_event",
    "chat_id": "chat",
    "image_id": "image",
}
