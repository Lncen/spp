"""自动化模块：通知记录定期清理 Celery 任务"""

import logging
from datetime import UTC, datetime, timedelta

from celery import shared_task
from sqlmodel import Session

from app.core.db import engine
from app.modules.notification.repositories.notification import purge_old_notifications
from app.modules.setting.application.setting_query import get_setting
from app.modules.setting.domain.constants import NOTIFICATION_RETENTION_DAYS

logger = logging.getLogger(__name__)

# 通知记录清理批次上限
NOTIFICATION_PURGE_BATCH_LIMIT = 500

# 保留期默认值（天），由全局设置 notification_retention_days 覆盖
DEFAULT_NOTIFICATION_RETENTION_DAYS = 30


@shared_task(
    ignore_result=False,
    name=(
        "app.modules.automation.infrastructure.tasks."
        "cleanup_notification_records"
    ),
)
def cleanup_notification_records() -> dict:
    """定期清理通知记录：物理删除超过保留期的通知及其投递记录。

    保留天数由全局设置 `notification_retention_days` 控制，默认 30 天；
    由 beat 每天低频触发，分批处理避免长事务。
    """
    stats = {"purged": 0, "errors": []}
    try:
        with Session(engine) as session:
            retention_days = _get_retention_days(session=session)
            before = datetime.now(UTC) - timedelta(days=retention_days)
            while True:
                purged = purge_old_notifications(
                    session=session,
                    before=before,
                    limit=NOTIFICATION_PURGE_BATCH_LIMIT,
                )
                stats["purged"] += purged
                if purged < NOTIFICATION_PURGE_BATCH_LIMIT:
                    break
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append(str(exc))
        logger.exception("通知记录清理异常")
    return stats


def _get_retention_days(*, session: Session) -> int:
    """读取全局设置的通知保留天数，非法值回退默认 30 天。"""
    try:
        days = int(
            get_setting(
                session=session,
                key=NOTIFICATION_RETENTION_DAYS,
            )
        )
    except (TypeError, ValueError):
        days = DEFAULT_NOTIFICATION_RETENTION_DAYS
    return max(1, days)
