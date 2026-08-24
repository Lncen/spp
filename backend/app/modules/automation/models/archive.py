"""自动化模块：自动化任务归档数据模型"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlmodel import Field, SQLModel

from app.core.mixin.models import UUIDPrimaryKeyMixin
from app.core.time import get_datetime_cn
from app.modules.automation.domain.constants import AutomationTaskStatus


class AutomationTaskArchive(UUIDPrimaryKeyMixin, SQLModel, table=True):
    """自动化任务归档：终态任务从任务池移入，按全局设置保留期物理清理"""

    __tablename__ = "automation_task_archives"

    task_id: uuid.UUID = Field(
        index=True,
        nullable=False,
        title="原任务 ID",
        description="归档前任务池中的任务 ID，用于恢复重新入队",
    )
    task_type: str = Field(
        max_length=64,
        index=True,
        nullable=False,
        title="任务类型",
        description="对应 Executor 注册的任务类型",
    )
    event_id: uuid.UUID | None = Field(
        default=None,
        index=True,
        title="来源事件 ID",
        description="生成该任务的事件 ID",
    )
    rule_id: uuid.UUID | None = Field(
        default=None,
        index=True,
        title="来源规则 ID",
        description="生成该任务的规则 ID",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        title="任务参数",
        description="执行所需参数，JSON 存储",
    )
    status: AutomationTaskStatus = Field(
        default=AutomationTaskStatus.SUCCESS,
        sa_type=String(20),
        index=True,
        nullable=False,
        title="任务状态",
        description="归档时的终态（success / failed / canceled）",
    )
    priority: int = Field(
        default=0,
        index=True,
        title="优先级",
        description="数值越大越优先执行",
    )
    execute_at: datetime = Field(
        default_factory=get_datetime_cn,
        sa_type=DateTime(timezone=True),
        index=True,
        nullable=False,
        title="计划执行时间",
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
    created_at: datetime = Field(
        default_factory=get_datetime_cn,
        sa_type=DateTime(timezone=True),
        nullable=False,
        title="创建时间",
        description="任务创建时间（北京时间）",
    )
    claimed_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        title="认领时间",
        description="worker 原子认领任务的时刻（北京时间）",
    )
    started_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        title="开始执行时间",
        description="Executor 开始执行的时刻（北京时间）",
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        title="完成时间",
        description="成功或失败终态时刻（北京时间）",
    )
    archived_at: datetime = Field(
        default_factory=get_datetime_cn,
        sa_type=DateTime(timezone=True),
        index=True,
        nullable=False,
        title="归档时间",
        description="移入归档表的时刻（北京时间），超过保留期后被物理删除",
    )
