"""自动化模块：计划任务应用服务

按业务能力归组：计划任务查询、更新、启停、立即执行，以及 Celery 任务清单与执行状态。
"""

import json
from typing import Any

from kombu.utils.json import dumps
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy_celery_beat.models import (
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
)

from app.modules.automation.domain.validation import validate_schedule_input
from app.modules.automation.infrastructure.celery import (
    fetch_task_status,
    send_task_now,
)
from app.modules.automation.infrastructure.celery import (
    list_task_options as list_celery_task_options,
)
from app.modules.automation.repositories.schedule import (
    build_crontab_schedule,
    build_interval_schedule,
    cleanup_orphan_schedules,
    count_tasks,
    get_task_or_404,
    list_tasks,
    task_schedule_type,
)
from app.modules.automation.schemas import (
    CrontabScheduleIn,
    IntervalScheduleIn,
    SchedulePublic,
    SchedulesPublic,
    ScheduleUpdate,
    TaskOption,
    TaskStatusPublic,
)


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


def update_schedule(
    *,
    session: Session,
    task_id: int,
    schedule_in: ScheduleUpdate,
) -> PeriodicTask:
    """更新计划任务，支持切换 crontab / interval。"""
    task = get_task_or_404(session=session, task_id=task_id)
    update_dict = schedule_in.model_dump(exclude_unset=True)
    schedule_type = update_dict.pop("schedule_type", None)
    crontab_in = update_dict.pop("crontab", None)
    interval_in = update_dict.pop("interval", None)
    if crontab_in is not None and not isinstance(crontab_in, CrontabScheduleIn):
        crontab_in = CrontabScheduleIn.model_validate(crontab_in)
    if interval_in is not None and not isinstance(interval_in, IntervalScheduleIn):
        interval_in = IntervalScheduleIn.model_validate(interval_in)

    has_crontab = crontab_in is not None
    has_interval = interval_in is not None
    if schedule_type is not None or has_crontab or has_interval:
        current_type = task_schedule_type(task)
        new_type = schedule_type or current_type
        # 仅切换类型（未提供配置）时无法构造 schedule，交由校验拦截；
        # 类型未变化且未提供配置时只更新其他字段，不做调度校验
        if new_type != current_type or has_crontab or has_interval:
            validate_schedule_input(
                schedule_type=new_type,
                has_crontab=has_crontab,
                has_interval=has_interval,
            )
        if crontab_in is not None:
            task.schedule_model = build_crontab_schedule(
                session=session,
                minute=crontab_in.minute,
                hour=crontab_in.hour,
                day_of_week=crontab_in.day_of_week,
                day_of_month=crontab_in.day_of_month,
                month_of_year=crontab_in.month_of_year,
                timezone=crontab_in.timezone,
            )
        elif interval_in is not None:
            task.schedule_model = build_interval_schedule(
                session=session,
                every=interval_in.every,
                period=interval_in.period.value,
            )

    nullable_update_fields = {"description"}
    update_dict = {
        key: value
        for key, value in update_dict.items()
        if value is not None or key in nullable_update_fields
    }

    for field, value in update_dict.items():
        if field in {"args", "kwargs"} and value is not None:
            setattr(task, field, dumps(value))
        else:
            setattr(task, field, value)

    session.add(task)
    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise ValueError("计划名称已存在") from e
    session.refresh(task)
    cleanup_orphan_schedules(session=session)
    session.commit()
    session.refresh(task)
    return task


def toggle_schedule(*, session: Session, task_id: int) -> PeriodicTask:
    """启用或停用计划任务。"""
    task = get_task_or_404(session=session, task_id=task_id)
    task.enabled = not task.enabled
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def run_schedule_now(*, session: Session, task_id: int) -> str:
    """立即发送一次任务，不改变原计划。"""
    task = get_task_or_404(session=session, task_id=task_id)
    args = json.loads(task.args or "[]")
    kwargs = json.loads(task.kwargs or "{}")
    return send_task_now(task_name=task.task, args=args, kwargs=kwargs)


def list_task_options() -> list[TaskOption]:
    """列出可配置的 Celery 任务。"""
    return list_celery_task_options()


def get_task_status(task_id: str) -> TaskStatusPublic:
    """查询 Celery 任务执行状态。"""
    return fetch_task_status(task_id)
