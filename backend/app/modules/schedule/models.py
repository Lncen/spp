"""计划任务模块：数据库模型"""

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin


class ScheduleRun(BaseModelMixin, SQLModel, table=True):
    """计划任务失败执行记录"""

    task_id: str = Field(
        unique=True,
        index=True,
        nullable=False,
        title="Celery 任务 ID",
        description="任务执行唯一 ID，Celery 重试会复用同一 ID",
    )
    task_name: str = Field(
        index=True,
        nullable=False,
        max_length=255,
        title="任务名称",
        description="Celery 任务完整路径",
    )
    schedule_id: int | None = Field(
        default=None,
        index=True,
        title="计划 ID",
        description="关联的 periodic_task ID，自动执行时可能为空",
    )
    schedule_name: str | None = Field(
        default=None,
        max_length=255,
        title="计划名称",
        description="计划名称冗余，便于列表展示",
    )
    error_type: str | None = Field(
        default=None,
        max_length=255,
        title="异常类型",
    )
    error_message: str = Field(
        nullable=False,
        title="异常信息",
        description="失败原因摘要",
    )
    traceback: str | None = Field(
        default=None,
        title="异常堆栈",
        description="失败堆栈，写入时截断",
    )
    finished_at: datetime | None = Field(
        default=None,
        title="失败时间",
        description="任务失败时刻（UTC）",
    )
