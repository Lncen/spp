"""计划任务模块：服务层"""

import json
from typing import Any

from celery.result import AsyncResult
from kombu.utils.json import dumps
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy_celery_beat.models import (
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
)
from sqlmodel import func, select

from app.core.celery_app import celery_app, discover_tasks
from app.modules.schedule.models import ScheduleRun
from app.modules.schedule.schemas import (
    CrontabScheduleIn,
    IntervalScheduleIn,
    ScheduleCreate,
    SchedulePublic,
    ScheduleType,
    ScheduleUpdate,
    TaskOption,
    TaskStatusPublic,
)

TASK_LABELS: dict[str, str] = {
    "app.tasks.cleanup.cleanup_expired_data": "清理过期数据",
    "app.tasks.cleanup.cleanup_schedule_runs": "清理失败celery执行记录",
    "app.tasks.order.fulfill_paid_orders_periodic": "向上游下单已付款订单",
    "app.tasks.order.sync_order_status_periodic": "同步订单状态",
    "app.tasks.product.sync_product_status": "同步商品状态",
    "app.tasks.supplier.sync_upstream_products": "同步供应商商品",
}


def _build_schedule_model(
    session: Session,
    schedule_type: ScheduleType,
    crontab_in: CrontabScheduleIn | None,
    interval_in: IntervalScheduleIn | None,
):
    """根据输入构造可复用的 schedule 模型并写入 session。"""
    if schedule_type == ScheduleType.CRONTAB:
        if not crontab_in:
            raise ValueError("schedule_type=crontab 时必须提供 crontab 配置")
        spec = crontab_in.model_dump()
        timezone = spec.pop("timezone")
        model = CrontabSchedule(timezone=timezone, **spec)
    else:
        if not interval_in:
            raise ValueError("schedule_type=interval 时必须提供 interval 配置")
        model = IntervalSchedule(
            every=interval_in.every,
            period=interval_in.period.value,
        )
    session.add(model)
    session.flush()
    return model


def _schedule_to_public(task: PeriodicTask) -> SchedulePublic:
    """将 PeriodicTask 转为公开响应模型。"""
    schedule_model = task.schedule_model
    crontab_data: dict[str, Any] | None = None
    interval_data: dict[str, Any] | None = None
    schedule_description: str | None = None
    schedule_type = _task_schedule_type(task)

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


def _task_schedule_type(task: PeriodicTask) -> ScheduleType:
    """根据 discriminator 推断调度类型。"""
    if task.discriminator == "crontabschedule":
        return ScheduleType.CRONTAB
    return ScheduleType.INTERVAL


def _cleanup_orphan_schedules(session: Session) -> None:
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


def list_task_options() -> list[TaskOption]:
    """列出可配置的 Celery 任务。"""
    discover_tasks()
    options: list[TaskOption] = []
    for name, task in sorted(celery_app.tasks.items()):
        if not name.startswith("app.tasks."):
            continue
        signature = None
        if getattr(task, "__wrapped__", None) is not None:
            try:
                signature = str(task.__wrapped__)
            except Exception:  # noqa: BLE001
                signature = None
        options.append(
            TaskOption(
                value=name,
                label=TASK_LABELS.get(name, name),
                signature=signature,
                doc=task.__doc__,
            )
        )
    return options


def create_schedule(
    session: Session,
    schedule_in: ScheduleCreate,
) -> PeriodicTask:
    """创建计划任务。"""
    schedule_model = _build_schedule_model(
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


def update_schedule(
    session: Session,
    task: PeriodicTask,
    schedule_in: ScheduleUpdate,
) -> PeriodicTask:
    """更新计划任务，支持切换 crontab / interval。"""
    update_dict = schedule_in.model_dump(exclude_unset=True)
    schedule_type = update_dict.pop("schedule_type", None)
    crontab_in = update_dict.pop("crontab", None)
    interval_in = update_dict.pop("interval", None)
    if crontab_in is not None and not isinstance(crontab_in, CrontabScheduleIn):
        crontab_in = CrontabScheduleIn.model_validate(crontab_in)
    if interval_in is not None and not isinstance(interval_in, IntervalScheduleIn):
        interval_in = IntervalScheduleIn.model_validate(interval_in)

    if schedule_type is not None or crontab_in is not None or interval_in is not None:
        current_type = _task_schedule_type(task)
        new_type = schedule_type or current_type
        if new_type != current_type:
            if new_type == ScheduleType.CRONTAB and crontab_in is None:
                raise ValueError("schedule_type=crontab 时必须提供 crontab 配置")
            if new_type == ScheduleType.INTERVAL and interval_in is None:
                raise ValueError("schedule_type=interval 时必须提供 interval 配置")
            old_model = task.schedule_model
            new_model = _build_schedule_model(
                session=session,
                schedule_type=new_type,
                crontab_in=crontab_in,
                interval_in=interval_in,
            )
            task.schedule_model = new_model
            if old_model is not None:
                session.delete(old_model)
        else:
            current = task.schedule_model
            if isinstance(current, CrontabSchedule) and crontab_in is not None:
                spec = crontab_in.model_dump()
                for key, value in spec.items():
                    setattr(current, key, value)
            elif isinstance(current, IntervalSchedule) and interval_in is not None:
                current.every = interval_in.every
                current.period = interval_in.period.value

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
    _cleanup_orphan_schedules(session)
    session.commit()
    session.refresh(task)
    return task


def delete_schedule(session: Session, task: PeriodicTask) -> None:
    """删除计划任务并清理其 schedule。"""
    schedule_model = task.schedule_model
    session.delete(task)
    if schedule_model is not None:
        session.delete(schedule_model)
    session.commit()


def toggle_schedule(session: Session, task: PeriodicTask) -> PeriodicTask:
    """启用 / 停用计划任务。"""
    task.enabled = not task.enabled
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def run_schedule_now(task: PeriodicTask) -> str:
    """立即发送一次任务，不改变原计划。"""
    args = json.loads(task.args or "[]")
    kwargs = json.loads(task.kwargs or "{}")
    result = celery_app.send_task(task.task, args=args, kwargs=kwargs)
    return result.id


def get_task_status(task_id: str) -> TaskStatusPublic:
    """查询 Celery 任务执行状态（结果来自 Redis result backend）"""
    result = AsyncResult(task_id, app=celery_app)
    if result.state in {"PENDING", "STARTED", "RETRY"}:
        return TaskStatusPublic(status=result.state, success=None)
    if result.state == "SUCCESS":
        return TaskStatusPublic(
            status=result.state,
            success=True,
            result=result.result,
        )
    return TaskStatusPublic(status=result.state, success=False)


def list_failed_runs(
    session: Session,
    skip: int = 0,
    limit: int = 100,
    task_name: str | None = None,
) -> tuple[list[ScheduleRun], int]:
    """分页查询失败执行记录（按失败时间倒序）。"""
    statement = select(ScheduleRun).order_by(ScheduleRun.created_at.desc())
    count_statement = select(func.count()).select_from(ScheduleRun)
    if task_name:
        statement = statement.where(ScheduleRun.task_name == task_name)
        count_statement = count_statement.where(
            ScheduleRun.task_name == task_name
        )
    runs = session.exec(statement.offset(skip).limit(limit)).all()
    count = session.exec(count_statement).one()
    return runs, count
