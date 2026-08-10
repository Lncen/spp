"""自动化模块：任务池扫描执行 Celery 任务"""

import logging
from datetime import UTC, datetime, timedelta

from celery import shared_task
from sqlmodel import Session

from app.core.db import engine
from app.modules.automation.infrastructure.executors import (
    ExecutorTerminalError,
    get_executor,
)
from app.modules.automation.repositories.task import (
    archive_finished_tasks,
    claim_due_tasks,
    mark_failed,
    mark_success,
    purge_archives,
    recover_stale_running_tasks,
)
from app.modules.setting.constants import AUTOMATION_TASK_RETENTION_DAYS
from app.modules.setting.service import get_setting

logger = logging.getLogger(__name__)

# 每次扫描最多认领并执行的任务数
SCAN_LIMIT = 500

# 运行中任务超过该时长未推进视为 worker 失联，恢复为待执行
STALE_RUNNING_MINUTES = 10

# 归档数据清理批次上限
ARCHIVE_BATCH_LIMIT = 500
PURGE_BATCH_LIMIT = 5000

# 保留期默认值（天），由全局设置 automation_task_retention_days 覆盖
DEFAULT_RETENTION_DAYS = 3


@shared_task(
    ignore_result=False,
    name="app.modules.automation.infrastructure.tasks.automation_task_scan",
)
def automation_task_scan() -> dict:
    """扫描到期任务池并执行：原子认领 → Executor 执行 → 记录结果 / 重试。

    由 beat 低频触发，单次执行多个任务，避免每个任务单独占用 beat 调度。
    执行前先恢复失联的 running 任务（worker 崩溃后自动重新排队）。
    """
    stats = {
        "claimed": 0,
        "success": 0,
        "failed": 0,
        "retried": 0,
        "recovered": 0,
        "errors": [],
    }
    try:
        with Session(engine) as session:
            stats["recovered"] = recover_stale_running_tasks(
                session=session,
                before=datetime.now(UTC)
                - timedelta(minutes=STALE_RUNNING_MINUTES),
            )
            tasks = claim_due_tasks(
                session=session,
                limit=SCAN_LIMIT,
                now=datetime.now(UTC),
            )
            stats["claimed"] = len(tasks)
            for task in tasks:
                # 推进心跳，防止长批次执行中任务被其他实例误判为失联
                task.updated_at = datetime.now(UTC)
                session.add(task)
                session.commit()
                try:
                    executor_cls = get_executor(task.task_type)
                    executor_cls().execute(task=task)
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    session.refresh(task)
                    before = task.retry_count
                    mark_failed(
                        session=session,
                        task=task,
                        error_message=str(exc),
                        now=datetime.now(UTC),
                        terminal=isinstance(exc, ExecutorTerminalError),
                    )
                    if task.retry_count > before:
                        stats["retried"] += 1
                    else:
                        stats["failed"] += 1
                    logger.warning("自动化任务 %s 执行失败: %s", task.id, exc)
                else:
                    mark_success(session=session, task=task)
                    stats["success"] += 1
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append(str(exc))
        logger.exception("自动化任务池扫描异常")
    return stats


@shared_task(
    ignore_result=False,
    name=(
        "app.modules.automation.infrastructure.tasks."
        "cleanup_automation_task_archives"
    ),
)
def cleanup_automation_task_archives() -> dict:
    """定期清理自动化任务数据：归档遗留终态任务 + 物理删除超保留期归档数据。

    保留天数由全局设置 `automation_task_retention_days` 控制，默认 3 天；
    由 beat 每天低频触发，分批处理避免长事务。
    """
    stats = {"archived": 0, "purged": 0, "errors": []}
    try:
        with Session(engine) as session:
            retention_days = _get_retention_days(session=session)
            before = datetime.now(UTC) - timedelta(days=retention_days)
            while True:
                archived = archive_finished_tasks(
                    session=session,
                    before=before,
                    limit=ARCHIVE_BATCH_LIMIT,
                )
                stats["archived"] += archived
                if archived < ARCHIVE_BATCH_LIMIT:
                    break
            while True:
                purged = purge_archives(
                    session=session,
                    before=before,
                    limit=PURGE_BATCH_LIMIT,
                )
                stats["purged"] += purged
                if purged < PURGE_BATCH_LIMIT:
                    break
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append(str(exc))
        logger.exception("自动化任务归档数据清理异常")
    return stats


def _get_retention_days(*, session: Session) -> int:
    """读取全局设置的归档保留天数，非法值回退默认 3 天。"""
    try:
        days = int(
            get_setting(
                session=session,
                key=AUTOMATION_TASK_RETENTION_DAYS,
            )
        )
    except (TypeError, ValueError):
        days = DEFAULT_RETENTION_DAYS
    return max(1, days)
