"""自动化模块：客服会话定期清理 Celery 任务"""

import logging
from datetime import timedelta

from celery import shared_task
from sqlmodel import Session

from app.core.db import engine
from app.core.time import get_datetime_cn
from app.modules.automation.infrastructure.tasks.retention import (
    get_retention_days,
)
from app.modules.customer_service.repositories.conversation import (
    purge_old_conversations,
)
from app.modules.setting.domain.constants import CONVERSATION_RETENTION_DAYS

logger = logging.getLogger(__name__)

# 会话清理批次上限
CONVERSATION_PURGE_BATCH_LIMIT = 500

# 保留期默认值（天），由全局设置 conversation_retention_days 覆盖
DEFAULT_CONVERSATION_RETENTION_DAYS = 7


@shared_task(
    ignore_result=False,
    name=(
        "app.modules.automation.infrastructure.tasks."
        "cleanup_conversations"
    ),
)
def cleanup_conversations() -> dict:
    """定期清理客服会话：物理删除超过保留期的会话及其全部消息。

    保留天数由全局设置 `conversation_retention_days` 控制，默认 7 天；
    超期以最后消息时间为准（无消息时取创建时间），不区分 open / closed；
    由 beat 每天低频触发，分批处理避免长事务。
    """
    stats = {"purged": 0, "errors": []}
    try:
        with Session(engine) as session:
            retention_days = get_retention_days(
                session=session,
                key=CONVERSATION_RETENTION_DAYS,
                default=DEFAULT_CONVERSATION_RETENTION_DAYS,
            )
            before = get_datetime_cn() - timedelta(days=retention_days)
            while True:
                purged = purge_old_conversations(
                    session=session,
                    before=before,
                    limit=CONVERSATION_PURGE_BATCH_LIMIT,
                )
                stats["purged"] += purged
                if purged < CONVERSATION_PURGE_BATCH_LIMIT:
                    break
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append(str(exc))
        logger.exception("客服会话清理异常")
    return stats
