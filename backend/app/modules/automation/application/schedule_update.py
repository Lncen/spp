"""自动化模块：更新计划任务应用服务"""

from kombu.utils.json import dumps
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy_celery_beat.models import PeriodicTask

from app.modules.automation.domain.validation import validate_schedule_input
from app.modules.automation.repositories.schedule import (
    build_schedule_model,
    cleanup_orphan_schedules,
    get_task_or_404,
    task_schedule_type,
)
from app.modules.automation.schemas import (
    CrontabScheduleIn,
    IntervalScheduleIn,
    ScheduleUpdate,
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

    if schedule_type is not None or crontab_in is not None or interval_in is not None:
        current_type = task_schedule_type(task)
        new_type = schedule_type or current_type
        changing_type = new_type != current_type
        has_schedule_config = crontab_in is not None or interval_in is not None
        if changing_type or has_schedule_config:
            validate_schedule_input(
                schedule_type=new_type,
                crontab=crontab_in,
                interval=interval_in,
            )
        if has_schedule_config:
            new_model = build_schedule_model(
                session=session,
                schedule_type=new_type,
                crontab_in=crontab_in,
                interval_in=interval_in,
            )
            task.schedule_model = new_model

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
