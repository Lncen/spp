"""系统日志数据模型：记录系统发生了什么"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime
from sqlmodel import Field, SQLModel

from app.core.mixin.models import UUIDPrimaryKeyMixin
from app.core.time import get_datetime_cn


class SystemLog(UUIDPrimaryKeyMixin, SQLModel, table=True):
    """系统日志：由全局事件总线产生，面向追踪与问题定位"""

    __tablename__ = "system_logs"

    level: str = Field(
        max_length=16,
        index=True,
        nullable=False,
        title="日志级别",
        description="info / warning / error / critical",
    )
    event_type: str = Field(
        max_length=128,
        index=True,
        nullable=False,
        title="事件类型",
        description="统一命名的事件类型，如 order.fulfillment_failed",
    )
    module: str = Field(
        max_length=64,
        index=True,
        nullable=False,
        title="所属模块",
        description="从事件类型推导出的业务模块，如 order / supplier / automation",
    )
    actor_type: str | None = Field(
        default=None,
        max_length=32,
        title="操作者类型",
        description="system / user / automation，事件未携带时为 system",
    )
    actor_id: uuid.UUID | None = Field(
        default=None,
        index=True,
        title="操作者 ID",
        description="用户或系统对象 ID；事件未携带时为 None",
    )
    resource_type: str | None = Field(
        default=None,
        max_length=64,
        index=True,
        title="目标对象类型",
        description="如 order / product / supplier / user",
    )
    resource_id: str | None = Field(
        default=None,
        max_length=128,
        index=True,
        title="目标对象 ID",
        description="业务资源 ID 的字符串快照",
    )
    event_id: uuid.UUID | None = Field(
        default=None,
        index=True,
        title="来源事件 ID",
        description="产生该日志的 AutomationEvent ID，不建外键以解耦清理策略",
    )
    request_id: str | None = Field(
        default=None,
        max_length=128,
        index=True,
        title="请求 ID",
        description="产生该事件的 HTTP 请求 ID",
    )
    trace_id: str | None = Field(
        default=None,
        max_length=128,
        index=True,
        title="链路 ID",
        description="跨服务或跨任务的追踪 ID",
    )
    business_id: str | None = Field(
        default=None,
        max_length=128,
        index=True,
        title="业务 ID",
        description="业务唯一标识，如订单号",
    )
    task_id: str | None = Field(
        default=None,
        max_length=128,
        index=True,
        title="任务 ID",
        description="关联的自动化任务或 Celery 任务 ID",
    )
    status: str | None = Field(
        default=None,
        max_length=32,
        index=True,
        title="结果状态",
        description="success / failed / unknown",
    )
    error_code: str | None = Field(
        default=None,
        max_length=128,
        title="错误码",
        description="稳定错误码，便于聚合统计",
    )
    error_message: str | None = Field(
        default=None,
        max_length=2000,
        title="错误信息",
        description="最近一次错误的可读信息",
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        title="上下文数据",
        description="事件载荷快照，便于从订单/用户/任务反查完整上下文",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_cn,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
        index=True,
        nullable=False,
        title="创建时间",
        description="日志落库时间（北京时间）",
    )
