"""自动化模块：自动化任务数据模型（任务池）"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlmodel import Field, SQLModel

from app.core.mixin.models import (
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    get_datetime_utc,
)
from app.modules.automation.domain.constants import AutomationTaskStatus


class AutomationTask(UUIDPrimaryKeyMixin, TimestampMixin, SQLModel, table=True):
    """自动化执行任务（任务池）：由 worker 原子认领并交给 Executor 执行"""

    __tablename__ = "automation_tasks"

    task_type: str = Field(
        max_length=64,
        index=True,
        nullable=False,
        title="任务类型",
        description="对应 Executor 注册的任务类型",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        title="任务参数",
        description="执行所需参数，JSON 存储",
    )
    event_id: uuid.UUID | None = Field(
        default=None,
        index=True,
        title="来源事件 ID",
        description="生成该任务的事件 ID，手动创建任务时为空",
    )
    rule_id: uuid.UUID | None = Field(
        default=None,
        index=True,
        title="来源规则 ID",
        description="生成该任务的规则 ID，手动创建任务时为空",
    )
    status: AutomationTaskStatus = Field(
        default=AutomationTaskStatus.PENDING,
        sa_type=String(20),
        index=True,
        nullable=False,
        title="任务状态",
        description="pending=待执行 / running=执行中 / success=成功 / failed=失败 / canceled=已取消",
    )
    priority: int = Field(
        default=0,
        index=True,
        title="优先级",
        description="数值越大越优先执行",
    )
    execute_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
        index=True,
        nullable=False,
        title="计划执行时间",
        description="到点后才会被 worker 认领",
    )
    retry_count: int = Field(
        default=0,
        nullable=False,
        title="已重试次数",
        description="失败自动重试的累计次数",
    )
    max_retry: int = Field(
        default=3,
        nullable=False,
        title="最大重试次数",
        description="超过后任务进入失败终态",
    )
    last_error: str | None = Field(
        default=None,
        max_length=2000,
        title="最近错误",
        description="最近一次失败原因",
    )
    claimed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        index=True,
        title="认领时间",
        description="worker 原子认领任务的时刻（UTC）",
    )
    started_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        title="开始执行时间",
        description="Executor 开始执行的时刻（UTC）",
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        title="完成时间",
        description="成功或失败终态时刻（UTC）",
    )
