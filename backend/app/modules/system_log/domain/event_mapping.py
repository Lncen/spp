"""系统日志事件映射规则"""

import uuid
from dataclasses import dataclass
from typing import Any

from app.modules.automation.models import AutomationEvent
from app.modules.system_log.domain.constants import (
    RESOURCE_KEY_MAP,
    ActorType,
    LogLevel,
    SystemLogStatus,
)


@dataclass(frozen=True)
class SystemLogRecord:
    """从 AutomationEvent 推导出的系统日志记录"""

    level: LogLevel
    event_type: str
    module: str
    actor_type: str
    actor_id: uuid.UUID | None
    resource_type: str | None
    resource_id: str | None
    event_id: uuid.UUID
    request_id: str | None
    trace_id: str | None
    business_id: str | None
    task_id: str | None
    status: SystemLogStatus
    error_code: str | None
    error_message: str | None
    context: dict[str, Any]


def derive_module(event_type: str) -> str:
    """从事件类型推导模块，缺省使用 system"""
    return event_type.split(".", 1)[0] if "." in event_type else "system"


def derive_level(event_type: str) -> LogLevel:
    """根据事件语义推导日志级别"""
    normalized = event_type.lower()
    if "unavailable" in normalized or "critical" in normalized:
        return LogLevel.CRITICAL
    if any(part in normalized for part in (".failed", "_failed", ".error", "_error")):
        return LogLevel.ERROR
    if any(part in normalized for part in ("slow", "warning", "unknown")):
        return LogLevel.WARNING
    return LogLevel.INFO


def derive_status(level: LogLevel) -> SystemLogStatus:
    """根据日志级别推导结果状态"""
    if level in (LogLevel.ERROR, LogLevel.CRITICAL):
        return SystemLogStatus.FAILED
    if level == LogLevel.WARNING:
        return SystemLogStatus.UNKNOWN
    return SystemLogStatus.SUCCESS


def _as_string(value: Any) -> str | None:
    """将载荷值安全转为字符串，用于日志检索字段"""
    if value is None:
        return None
    return str(value)


def _as_uuid(value: Any) -> uuid.UUID | None:
    """将载荷值安全解析为 UUID，非法值返回 None"""
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _find_resource(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    """从事件载荷中提取第一个可识别的资源类型与 ID"""
    for key, resource_type in RESOURCE_KEY_MAP.items():
        value = payload.get(key)
        if value not in (None, ""):
            return resource_type, _as_string(value)
    return None, None


def build_system_log_record(*, event: AutomationEvent) -> SystemLogRecord:
    """将 AutomationEvent 映射为结构化系统日志记录"""
    payload = event.payload or {}
    level = derive_level(event.event_type)
    resource_type, resource_id = _find_resource(payload)
    actor_id = _as_uuid(payload.get("actor_id"))
    actor_type = (
        ActorType.AUTOMATION
        if payload.get("task_id") or event.event_type.startswith("automation.")
        else ActorType.USER if actor_id else ActorType.SYSTEM
    )
    error = payload.get("error")
    error_code = None
    error_message = None
    if isinstance(error, dict):
        error_code = _as_string(error.get("code"))
        error_message = _as_string(error.get("message"))
    elif error is not None:
        error_message = _as_string(error)

    return SystemLogRecord(
        level=level,
        event_type=event.event_type,
        module=derive_module(event.event_type),
        actor_type=actor_type,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        event_id=event.id,
        request_id=_as_string(payload.get("request_id")),
        trace_id=_as_string(payload.get("trace_id")),
        business_id=_as_string(
            payload.get("business_id")
            or payload.get("order_no")
        ),
        task_id=_as_string(payload.get("task_id")),
        status=derive_status(level),
        error_code=error_code,
        error_message=error_message,
        context=dict(payload),
    )
