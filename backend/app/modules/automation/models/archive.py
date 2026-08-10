"""自动化模块：自动化任务归档数据模型"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin, get_datetime_utc
from app.modules.automation.domain.constants import AutomationTaskStatus


class AutomationTaskArchive(BaseModelMixin, SQLModel, table=True):
    """自动化任务归档：终态任务从任务池移入，按全局设置保留期物理清理"""

    __tablename__ = "automation_task_archives"

    task_type: str = Field(
        max_length=64,
        index=True,
        nullable=False,
        title="任务类型",
        description="对应 Executor 注册的任务类型",
    )
    status: AutomationTaskStatus = Field(
        default=AutomationTaskStatus.SUCCESS,
        sa_type=String(20),
        index=True,
        nullable=False,
        title="任务状态",
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
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        title="任务参数",
        description="执行所需参数，JSON 存储",
    )
    error_message: str | None = Field(
        default=None,
        max_length=2000,
        title="错误信息",
        description="最近一次失败原因",
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        title="完成时间",
        description="成功或失败终态时刻（UTC）",
    )
    archived_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
        index=True,
        nullable=False,
        title="归档时间",
        description="移入归档表的时刻（UTC），超过保留期后被物理删除",
    )
