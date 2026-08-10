"""自动化模块：计划任务查询应用服务"""

import json
from typing import Any

from sqlalchemy_celery_beat.models import (
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
)
from sqlmodel import Session

from app.modules.automation.repositories.schedule import (
    count_tasks,
    get_task_or_404,
    list_tasks,
    task_schedule_type,
)
from app.modules.automation.schemas import SchedulePublic, SchedulesPublic

__all__ = [
    "get_schedule_public",
    "list_schedules",
    "to_schedule_public",
]


def list_schedules(*, session: Session, skip: int, limit: int) -> SchedulesPublic:
    """分页获取计划任务列表。"""
    count = count_tasks(session=session)
    tasks = list_tasks(session=session, skip=skip, limit=limit)
    return SchedulesPublic(
        data=[to_schedule_public(task) for task in tasks],
        count=count,
    )


def get_schedule_public(*, session: Session, task_id: int) -> SchedulePublic:
    """按 ID 获取计划任务公开响应。"""
    return to_schedule_public(get_task_or_404(session=session, task_id=task_id))


def to_schedule_public(task: PeriodicTask) -> SchedulePublic:
    """将 PeriodicTask 转为公开响应模型。"""
    schedule_model = task.schedule_model
    crontab_data: dict[str, Any] | None = None
    interval_data: dict[str, Any] | None = None
    schedule_description: str | None = None
    schedule_type = task_schedule_type(task)

    if isinstance(schedule_model, CrontabSchedule):
        crontab_data = {
            "minute": schedule_model.minute,
            "hour": schedule_model.hour,
            "day_of_week": schedule_model.day_of_week,
            "day_of_month": schedule_model.day_of_month,
            "month_of_year": schedule_model.month_of_year,
            "timezone": schedule_model.timezone,
        }
        schedule_description = (
            f"{schedule_model.minute} {schedule_model.hour} "
            f"{schedule_model.day_of_month} {schedule_model.month_of_year} "
            f"{schedule_model.day_of_week} ({schedule_model.timezone})"
        )
    elif isinstance(schedule_model, IntervalSchedule):
        interval_data = {
            "every": schedule_model.every,
            "period": schedule_model.period.value,
        }
        schedule_description = (
            f"每 {schedule_model.every} "
            f"{schedule_model.period.value}"
        )

    return SchedulePublic(
        id=task.id,
        name=task.name,
        task=task.task,
        schedule_type=schedule_type,
        crontab=crontab_data,
        interval=interval_data,
        schedule_description=schedule_description,
        args=json.loads(task.args or "[]"),
        kwargs=json.loads(task.kwargs or "{}"),
        enabled=task.enabled,
        description=task.description or None,
        last_run_at=task.last_run_at,
        total_run_count=task.total_run_count or 0,
        date_changed=task.date_changed,
    )
