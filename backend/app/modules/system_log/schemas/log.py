"""系统日志 API 数据传输对象"""

import uuid
from datetime import datetime
from typing import Any

from sqlmodel import SQLModel


class SystemLogPublic(SQLModel):
    """系统日志对外展示结构"""

    id: uuid.UUID
    level: str
    event_type: str
    module: str
    actor_type: str | None = None
    actor_id: uuid.UUID | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    event_id: uuid.UUID | None = None
    request_id: str | None = None
    trace_id: str | None = None
    business_id: str | None = None
    task_id: str | None = None
    status: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    context: dict[str, Any]
    created_at: datetime


class SystemLogsPublic(SQLModel):
    """系统日志分页列表"""

    data: list[SystemLogPublic]
    count: int


class AuditLogPublic(SQLModel):
    """操作审计对外展示结构"""

    id: uuid.UUID
    actor_id: uuid.UUID | None = None
    actor_identifier: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    before: dict[str, Any]
    after: dict[str, Any]
    changes: dict[str, Any]
    ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    event_id: uuid.UUID | None = None
    created_at: datetime


class AuditLogsPublic(SQLModel):
    """操作审计分页列表"""

    data: list[AuditLogPublic]
    count: int
