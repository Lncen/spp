"""自动化模块：计划任务数据访问层"""

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session
from sqlalchemy_celery_beat.models import (
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
)
from sqlmodel import func, select

from app.modules.automation.domain.constants import ScheduleType
from app.modules.automation.schemas import CrontabScheduleIn, IntervalScheduleIn


def get_task_or_404(*, session: Session, task_id: int) -> PeriodicTask:
    """按 ID 获取计划任务，不存在时抛出 404。"""
    task = session.get(PeriodicTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="计划任务不存在")
    return task


def count_tasks(*, session: Session) -> int:
    """统计计划任务总数。"""
    return session.exec(select(func.count()).select_from(PeriodicTask)).one()


def list_tasks(*, session: Session, skip: int, limit: int) -> list[PeriodicTask]:
    """分页查询计划任务。"""
    return session.exec(
        select(PeriodicTask).order_by(PeriodicTask.id).offset(skip).limit(limit)
    ).all()


def task_schedule_type(task: PeriodicTask) -> ScheduleType:
    """根据 discriminator 推断调度类型。"""
    if task.discriminator == "crontabschedule":
        return ScheduleType.CRONTAB
    return ScheduleType.INTERVAL


def build_schedule_model(
    *,
    session: Session,
    schedule_type: ScheduleType,
    crontab_in: CrontabScheduleIn | None,
    interval_in: IntervalScheduleIn | None,
) -> CrontabSchedule | IntervalSchedule:
    """根据输入构造可复用的 schedule 模型并写入 session。"""
    if schedule_type == ScheduleType.CRONTAB:
        if crontab_in is None:
            raise ValueError("schedule_type=crontab 时必须提供 crontab 配置")
        spec = crontab_in.model_dump()
        timezone = spec.pop("timezone")
        model = CrontabSchedule(timezone=timezone, **spec)
    else:
        if interval_in is None:
            raise ValueError("schedule_type=interval 时必须提供 interval 配置")
        model = IntervalSchedule(
            every=interval_in.every,
            period=interval_in.period.value,
        )
    session.add(model)
    session.flush()
    return model


def cleanup_orphan_schedules(*, session: Session) -> None:
    """清理没有任务引用的 schedule 记录，避免反复切换类型后残留孤儿数据。"""
    session.execute(
        delete(CrontabSchedule).where(
            ~CrontabSchedule.id.in_(
                select(PeriodicTask.schedule_id).where(
                    PeriodicTask.discriminator == "crontabschedule"
                )
            )
        )
    )
    session.execute(
        delete(IntervalSchedule).where(
            ~IntervalSchedule.id.in_(
                select(PeriodicTask.schedule_id).where(
                    PeriodicTask.discriminator == "intervalschedule"
                )
            )
        )
    )
    session.flush()
