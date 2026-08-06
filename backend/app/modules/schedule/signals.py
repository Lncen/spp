"""计划任务失败记录：Celery task_failure 信号处理"""

import logging
from datetime import UTC, datetime
from typing import Any

from celery import signals
from sqlalchemy import select
from sqlalchemy_celery_beat.models import PeriodicTask
from sqlmodel import Session

from app.core.db import engine
from app.modules.schedule.models import ScheduleRun

logger = logging.getLogger(__name__)

MAX_TRACEBACK_LENGTH = 8192
MAX_ERROR_MESSAGE_LENGTH = 2000


def _resolve_schedule(task_name: str) -> tuple[int | None, str | None]:
    """按任务名反查计划，返回 (schedule_id, schedule_name)。"""
    with Session(engine) as session:
        task = session.exec(
            select(PeriodicTask).where(PeriodicTask.task == task_name)
        ).first()
    if task is None:
        return None, None
    return task.id, task.name


def _record_failed_run(
    *,
    task_id: str,
    task_name: str,
    error_type: str | None,
    error_message: str,
    traceback: str | None,
) -> None:
    """按 task_id 写入或更新失败记录（重试复用同一 task_id）。"""
    schedule_id, schedule_name = _resolve_schedule(task_name)
    with Session(engine) as session:
        run = session.exec(
            select(ScheduleRun).where(ScheduleRun.task_id == task_id)
        ).first()
        if run is None:
            run = ScheduleRun(task_id=task_id, task_name=task_name)
            session.add(run)
        run.schedule_id = schedule_id
        run.schedule_name = schedule_name
        run.error_type = error_type
        run.error_message = error_message
        run.traceback = traceback
        run.finished_at = datetime.now(UTC)
        session.commit()


@signals.task_failure.connect
def handle_task_failure(
    sender: Any,
    task_id: str | None,
    exception: BaseException | None,
    traceback: str | None,
    **_kwargs: Any,
) -> None:
    """任务失败时写入失败记录（手动与 beat 自动执行统一覆盖）。"""
    task_name = getattr(sender, "name", None)
    if not task_id or not task_name:
        return
    try:
        _record_failed_run(
            task_id=task_id,
            task_name=task_name,
            error_type=type(exception).__name__ if exception else None,
            error_message=str(exception or "未知错误")[:MAX_ERROR_MESSAGE_LENGTH],
            traceback=(traceback or None)[:MAX_TRACEBACK_LENGTH],
        )
    except Exception:
        logger.exception("记录任务失败信息失败 task_id=%s", task_id)
