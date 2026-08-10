"""自动化模块：创建计划任务应用服务"""

from kombu.utils.json import dumps
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy_celery_beat.models import PeriodicTask

from app.modules.automation.domain.validation import validate_schedule_input
from app.modules.automation.repositories.schedule import build_schedule_model
from app.modules.automation.schemas import ScheduleCreate


def create_schedule(*, session: Session, schedule_in: ScheduleCreate) -> PeriodicTask:
    """创建计划任务。"""
    validate_schedule_input(
        schedule_type=schedule_in.schedule_type,
        crontab=schedule_in.crontab,
        interval=schedule_in.interval,
    )
    schedule_model = build_schedule_model(
        session=session,
        schedule_type=schedule_in.schedule_type,
        crontab_in=schedule_in.crontab,
        interval_in=schedule_in.interval,
    )
    task = PeriodicTask(
        name=schedule_in.name,
        task=schedule_in.task,
        args=dumps(schedule_in.args or []),
        kwargs=dumps(schedule_in.kwargs or {}),
        enabled=schedule_in.enabled,
        description=schedule_in.description or "",
    )
    task.schedule_model = schedule_model
    session.add(task)
    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise ValueError(f"计划名称 {schedule_in.name!r} 已存在") from e
    session.refresh(task)
    return task
