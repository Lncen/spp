"""计划任务模块：API 请求与响应模型"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlmodel import Field, SQLModel


class ScheduleType(StrEnum):
    """计划任务调度类型"""

    CRONTAB = "crontab"
    INTERVAL = "interval"


class IntervalPeriod(StrEnum):
    """Interval 周期单位"""

    DAYS = "days"
    HOURS = "hours"
    MINUTES = "minutes"
    SECONDS = "seconds"
    MICROSECONDS = "microseconds"


class CrontabScheduleIn(SQLModel):
    """crontab 表达式输入"""

    minute: str = Field(default="*", max_length=240, title="分钟")
    hour: str = Field(default="*", max_length=96, title="小时")
    day_of_week: str = Field(default="*", max_length=64, title="星期")
    day_of_month: str = Field(default="*", max_length=124, title="日")
    month_of_year: str = Field(default="*", max_length=124, title="月")
    timezone: str = Field(default="Asia/Shanghai", max_length=64, title="时区")


class IntervalScheduleIn(SQLModel):
    """interval 间隔输入"""

    every: int = Field(default=1, ge=1, title="间隔数值")
    period: IntervalPeriod = Field(
        default=IntervalPeriod.MINUTES,
        title="间隔单位",
        description="days/hours/minutes/seconds/microseconds",
    )


class ScheduleBase(SQLModel):
    """计划任务基础属性"""

    name: str = Field(max_length=255, title="计划名称", description="唯一标识，beat 启动时会按名称同步")
    task: str = Field(max_length=255, title="任务名称", description="Celery 任务完整路径")
    schedule_type: ScheduleType = Field(title="调度类型")
    crontab: CrontabScheduleIn | None = Field(
        default=None,
        title="crontab 配置",
        description="schedule_type=crontab 时必填",
    )
    interval: IntervalScheduleIn | None = Field(
        default=None,
        title="interval 配置",
        description="schedule_type=interval 时必填",
    )
    args: list[Any] = Field(default_factory=list, title="位置参数")
    kwargs: dict[str, Any] = Field(default_factory=dict, title="关键字参数")
    enabled: bool = Field(default=True, title="是否启用")
    description: str | None = Field(default=None, max_length=1024, title="描述")


class ScheduleCreate(ScheduleBase):
    """创建计划任务请求"""


class ScheduleUpdate(SQLModel):
    """更新计划任务请求（全部可选）"""

    name: str | None = Field(default=None, max_length=255)
    task: str | None = Field(default=None, max_length=255)
    schedule_type: ScheduleType | None = None
    crontab: CrontabScheduleIn | None = None
    interval: IntervalScheduleIn | None = None
    args: list[Any] | None = None
    kwargs: dict[str, Any] | None = None
    enabled: bool | None = None
    description: str | None = Field(default=None, max_length=1024)


class CrontabSchedulePublic(CrontabScheduleIn):
    """crontab 配置响应"""


class IntervalSchedulePublic(IntervalScheduleIn):
    """interval 配置响应"""


class SchedulePublic(SQLModel):
    """计划任务公开响应"""

    id: int
    name: str
    task: str
    schedule_type: ScheduleType
    crontab: CrontabSchedulePublic | None = None
    interval: IntervalSchedulePublic | None = None
    schedule_description: str | None = Field(
        default=None,
        title="可读调度说明",
        description="如 every 30 minutes 或分时日月周表达式",
    )
    args: list[Any]
    kwargs: dict[str, Any]
    enabled: bool
    description: str | None = None
    last_run_at: datetime | None = None
    total_run_count: int = 0
    date_changed: datetime | None = None


class SchedulesPublic(SQLModel):
    """计划任务列表响应"""

    data: list[SchedulePublic]
    count: int


class TaskOption(SQLModel):
    """可选任务项，供前端下拉选择"""

    value: str = Field(title="任务路径")
    label: str = Field(title="展示名称")
    signature: str | None = Field(default=None, title="函数签名")
    doc: str | None = Field(default=None, title="任务说明")


class TaskOptionsPublic(SQLModel):
    """任务选项列表响应"""

    data: list[TaskOption]


class RunTaskPublic(SQLModel):
    """立即执行任务响应"""

    task_id: str = Field(title="Celery 任务 ID")


class TaskStatusPublic(SQLModel):
    """Celery 任务状态响应"""

    status: str = Field(title="任务状态")
    success: bool | None = Field(default=None, title="是否成功")
    result: dict[str, Any] | None = Field(default=None, title="任务结果")


class ScheduleRunPublic(SQLModel):
    """计划任务失败执行记录响应"""

    id: uuid.UUID
    task_id: str
    task_name: str
    schedule_id: int | None = None
    schedule_name: str | None = None
    error_type: str | None = None
    error_message: str
    traceback: str | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None


class ScheduleRunsPublic(SQLModel):
    """失败执行记录列表响应"""

    data: list[ScheduleRunPublic]
    count: int
