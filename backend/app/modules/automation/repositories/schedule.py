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


def build_crontab_schedule(
    *,
    session: Session,
    minute: str,
    hour: str,
    day_of_week: str,
    day_of_month: str,
    month_of_year: str,
    timezone: str,
) -> CrontabSchedule:
    """构造可复用的 crontab 配置并写入 session。"""
    model = CrontabSchedule(
        minute=minute,
        hour=hour,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        timezone=timezone,
    )
    session.add(model)
    session.flush()
    return model


def build_interval_schedule(
    *,
    session: Session,
    every: int,
    period: str,
) -> IntervalSchedule:
    """构造可复用的 interval 配置并写入 session。"""
    model = IntervalSchedule(every=every, period=period)
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
