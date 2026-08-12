"""自动化模块：自动化任务数据访问层"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, update
from sqlmodel import Session, func, select

from app.modules.automation.domain.constants import AutomationTaskStatus
from app.modules.automation.domain.execution import should_retry
from app.modules.automation.models import AutomationTask, AutomationTaskArchive

MAX_ERROR_MESSAGE_LENGTH = 2000

# 终态任务：进入终态即移入归档表，任务池只保留待执行 / 执行中任务
TERMINAL_STATUSES = (
    AutomationTaskStatus.SUCCESS,
    AutomationTaskStatus.FAILED,
    AutomationTaskStatus.CANCELED,
)


def create_task(
    *,
    session: Session,
    task_type: str,
    payload: dict[str, Any],
    priority: int = 0,
    execute_at: datetime | None = None,
    max_retry: int = 3,
    event_id: uuid.UUID | None = None,
    rule_id: uuid.UUID | None = None,
) -> AutomationTask:
    """创建任务记录（不提交，由调用方控制事务）。"""
    task = AutomationTask(
        task_type=task_type,
        payload=payload,
        event_id=event_id,
        rule_id=rule_id,
        priority=priority,
        execute_at=execute_at or datetime.now(UTC),
        max_retry=max_retry,
    )
    session.add(task)
    return task


def get_task_or_404(*, session: Session, task_id: uuid.UUID) -> AutomationTask:
    """按 ID 获取任务，不存在时抛出 404。"""
    task = session.get(AutomationTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="自动化任务不存在")
    return task


def count_tasks(
    *,
    session: Session,
    status: AutomationTaskStatus | None,
) -> int:
    """统计任务总数，可按状态过滤。"""
    stmt = select(func.count()).select_from(AutomationTask)
    if status is not None:
        stmt = stmt.where(AutomationTask.status == status)
    return session.exec(stmt).one()


def list_tasks(
    *,
    session: Session,
    skip: int,
    limit: int,
    status: AutomationTaskStatus | None,
) -> list[AutomationTask]:
    """分页查询任务，可按状态过滤，最新创建在前。"""
    stmt = (
        select(AutomationTask)
        .order_by(AutomationTask.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if status is not None:
        stmt = stmt.where(AutomationTask.status == status)
    return session.exec(stmt).all()


def count_archives(
    *,
    session: Session,
    status: AutomationTaskStatus | None,
) -> int:
    """统计归档任务总数，可按状态过滤。"""
    stmt = select(func.count()).select_from(AutomationTaskArchive)
    if status is not None:
        stmt = stmt.where(AutomationTaskArchive.status == status)
    return session.exec(stmt).one()


def list_archives(
    *,
    session: Session,
    skip: int,
    limit: int,
    status: AutomationTaskStatus | None,
) -> list[AutomationTaskArchive]:
    """分页查询归档任务，可按状态过滤，最新归档在前。"""
    stmt = (
        select(AutomationTaskArchive)
        .order_by(AutomationTaskArchive.archived_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if status is not None:
        stmt = stmt.where(AutomationTaskArchive.status == status)
    return session.exec(stmt).all()


def claim_due_tasks(
    *,
    session: Session,
    limit: int,
    now: datetime,
) -> list[AutomationTask]:
    """原子认领到期任务：UPDATE ... RETURNING 只返回本事务真正置为 running 的行，多 worker 不重复执行。"""
    ids = session.exec(
        select(AutomationTask.id)
        .where(
            AutomationTask.status == AutomationTaskStatus.PENDING,
            AutomationTask.execute_at <= now,
        )
        .order_by(
            AutomationTask.priority.desc(),
            AutomationTask.execute_at.asc(),
            AutomationTask.created_at.asc(),
        )
        .limit(limit)
    ).all()
    if not ids:
        return []
    claimed_ids = session.execute(
        update(AutomationTask)
        .where(
            AutomationTask.id.in_(ids),
            AutomationTask.status == AutomationTaskStatus.PENDING,
        )
        .values(
            status=AutomationTaskStatus.RUNNING,
            claimed_at=now,
        )
        .returning(AutomationTask.id)
    ).scalars().all()
    session.commit()
    if not claimed_ids:
        return []
    return session.exec(
        select(AutomationTask)
        .where(
            AutomationTask.id.in_(claimed_ids),
        )
        .order_by(AutomationTask.created_at.asc())
    ).all()


def recover_stale_running_tasks(
    *,
    session: Session,
    before: datetime,
) -> int:
    """恢复长时间未推进的 running 任务为待执行（worker 崩溃场景），返回恢复数量。"""
    result = session.exec(
        update(AutomationTask)
        .where(
            AutomationTask.status == AutomationTaskStatus.RUNNING,
            AutomationTask.updated_at.is_not(None),
            AutomationTask.updated_at < before,
        )
        .values(
            status=AutomationTaskStatus.PENDING,
            execute_at=datetime.now(UTC),
            claimed_at=None,
            started_at=None,
        )
    )
    session.commit()
    return result.rowcount or 0


def _move_to_archive(*, session: Session, task: AutomationTask) -> None:
    """将终态任务移入归档表并从任务池删除（同一事务，原任务 ID 存入 task_id）。"""
    archive = AutomationTaskArchive(
        task_id=task.id,
        task_type=task.task_type,
        event_id=task.event_id,
        rule_id=task.rule_id,
        status=task.status,
        priority=task.priority,
        execute_at=task.execute_at,
        retry_count=task.retry_count,
        max_retry=task.max_retry,
        payload=task.payload,
        last_error=task.last_error,
        claimed_at=task.claimed_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        created_at=task.created_at,
        archived_at=datetime.now(UTC),
    )
    session.add(archive)
    session.delete(task)


def mark_success(*, session: Session, task: AutomationTask) -> None:
    """标记任务执行成功并立即归档。"""
    task.status = AutomationTaskStatus.SUCCESS
    task.last_error = None
    task.finished_at = datetime.now(UTC)
    _move_to_archive(session=session, task=task)
    session.commit()


def mark_failed(
    *,
    session: Session,
    task: AutomationTask,
    error_message: str,
    now: datetime,
    terminal: bool = False,
) -> None:
    """标记任务执行失败：默认未达重试上限则回退 pending；terminal=True 表示业务已终态，跳过重试直接失败归档。"""
    task.last_error = error_message[:MAX_ERROR_MESSAGE_LENGTH]
    if not terminal and should_retry(
        retry_count=task.retry_count,
        max_retry=task.max_retry,
    ):
        task.retry_count += 1
        task.status = AutomationTaskStatus.PENDING
        task.execute_at = now
        task.finished_at = None
        task.claimed_at = None
        task.started_at = None
        session.add(task)
    else:
        task.status = AutomationTaskStatus.FAILED
        task.finished_at = now
        _move_to_archive(session=session, task=task)
    session.commit()


def reset_task(*, session: Session, task: AutomationTask) -> None:
    """手动重试：仅失败任务可回到待执行，重试计数清零后重新获得完整自动重试预算。"""
    if task.status != AutomationTaskStatus.FAILED:
        raise ValueError("仅失败任务可手动重试")
    task.status = AutomationTaskStatus.PENDING
    task.retry_count = 0
    task.execute_at = datetime.now(UTC)
    task.last_error = None
    task.claimed_at = None
    task.started_at = None
    task.finished_at = None
    session.add(task)
    session.commit()
    session.refresh(task)


def cancel_task(*, session: Session, task: AutomationTask) -> None:
    """取消任务：仅待执行任务可取消，取消后移入归档表。"""
    if task.status != AutomationTaskStatus.PENDING:
        raise ValueError("仅待执行任务可取消")
    task.status = AutomationTaskStatus.CANCELED
    task.last_error = None
    task.finished_at = datetime.now(UTC)
    _move_to_archive(session=session, task=task)
    session.commit()


def requeue_failed_task(
    *,
    session: Session,
    task_id: uuid.UUID,
) -> AutomationTask:
    """失败任务重新进入队列（重试计数清零）：任务池中直接重置；已归档则从归档表恢复。"""
    task = session.get(AutomationTask, task_id)
    if task is not None:
        if task.status != AutomationTaskStatus.FAILED:
            raise ValueError("仅失败任务可重新进入队列")
        reset_task(session=session, task=task)
        return task

    archived = session.exec(
        select(AutomationTaskArchive).where(
            AutomationTaskArchive.task_id == task_id
        )
    ).first()
    if archived is None:
        raise HTTPException(status_code=404, detail="自动化任务不存在或已归档")
    if archived.status != AutomationTaskStatus.FAILED:
        raise ValueError("仅失败任务可重新进入队列")
    task = AutomationTask(
        id=archived.task_id,
        task_type=archived.task_type,
        event_id=archived.event_id,
        rule_id=archived.rule_id,
        status=AutomationTaskStatus.PENDING,
        priority=archived.priority,
        execute_at=datetime.now(UTC),
        retry_count=0,
        max_retry=archived.max_retry,
        payload=archived.payload,
        last_error=None,
        claimed_at=None,
        started_at=None,
        finished_at=None,
        created_at=archived.created_at,
    )
    session.add(task)
    session.delete(archived)
    session.commit()
    session.refresh(task)
    return task


def archive_finished_tasks(
    *,
    session: Session,
    before: datetime,
    limit: int,
) -> int:
    """归档任务池中遗留的终态任务（旧数据兜底），返回归档数量。"""
    tasks = session.exec(
        select(AutomationTask)
        .where(
            AutomationTask.status.in_(TERMINAL_STATUSES),
            AutomationTask.finished_at.is_not(None),
            AutomationTask.finished_at <= before,
        )
        .order_by(AutomationTask.finished_at.asc())
        .limit(limit)
    ).all()
    for task in tasks:
        _move_to_archive(session=session, task=task)
    if tasks:
        session.commit()
    return len(tasks)


def purge_archives(
    *,
    session: Session,
    before: datetime,
    limit: int,
) -> int:
    """物理删除归档时间早于 before 的归档任务，返回删除数量。"""
    ids = session.exec(
        select(AutomationTaskArchive.id)
        .where(AutomationTaskArchive.archived_at < before)
        .limit(limit)
    ).all()
    if not ids:
        return 0
    session.exec(
        delete(AutomationTaskArchive).where(AutomationTaskArchive.id.in_(ids))
    )
    session.commit()
    return len(ids)
