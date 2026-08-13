"""自动化模块：归档与事件数据定期清理 Celery 任务"""

import logging
from datetime import UTC, datetime, timedelta

from celery import shared_task
from sqlmodel import Session

from app.core.db import engine
from app.modules.automation.repositories.event import purge_events
from app.modules.automation.repositories.task import (
    archive_finished_tasks,
    purge_archives,
)
from app.modules.setting.application.setting_query import get_setting
from app.modules.setting.domain.constants import AUTOMATION_TASK_RETENTION_DAYS

logger = logging.getLogger(__name__)

# 归档数据清理批次上限
ARCHIVE_BATCH_LIMIT = 500
PURGE_BATCH_LIMIT = 5000

# 保留期默认值（天），由全局设置 automation_task_retention_days 覆盖
DEFAULT_RETENTION_DAYS = 3


@shared_task(
    ignore_result=False,
    name=(
        "app.modules.automation.infrastructure.tasks."
        "cleanup_automation_task_archives"
    ),
)
def cleanup_automation_task_archives() -> dict:
    """定期清理自动化任务数据：归档遗留终态任务 + 物理删除超保留期归档与事件数据。

    保留天数由全局设置 `automation_task_retention_days` 控制，默认 3 天，
    归档与事件共用同一保留期同步清除；
    由 beat 每天低频触发，分批处理避免长事务。
    """
    stats = {"archived": 0, "purged": 0, "events_purged": 0, "errors": []}
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
            while True:
                events_purged = purge_events(
                    session=session,
                    before=before,
                    limit=PURGE_BATCH_LIMIT,
                )
                stats["events_purged"] += events_purged
                if events_purged < PURGE_BATCH_LIMIT:
                    break
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append(str(exc))
        logger.exception("自动化任务归档与事件数据清理异常")
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
