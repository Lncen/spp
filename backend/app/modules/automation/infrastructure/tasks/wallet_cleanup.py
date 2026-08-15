"""自动化模块：钱包流水数据定期清理 Celery 任务"""

import logging
from datetime import UTC, datetime, timedelta

from celery import shared_task
from sqlmodel import Session

from app.core.db import engine
from app.modules.setting.application.setting_query import get_setting
from app.modules.setting.domain.constants import WALLET_TRANSACTION_RETENTION_DAYS
from app.modules.wallet.repositories.wallet import purge_old_transactions

logger = logging.getLogger(__name__)

# 钱包流水清理批次上限
WALLET_PURGE_BATCH_LIMIT = 500

# 保留期默认值（天），由全局设置 wallet_transaction_retention_days 覆盖
DEFAULT_WALLET_RETENTION_DAYS = 7


@shared_task(
    ignore_result=False,
    name="app.modules.automation.infrastructure.tasks.cleanup_wallet_transactions",
)
def cleanup_wallet_transactions() -> dict:
    """定期清理钱包流水数据：物理删除超过保留期的交易流水。

    保留天数由全局设置 `wallet_transaction_retention_days` 控制，默认 7 天；
    仅清理 WalletTransaction 流水，不影响 Wallet 余额表；
    由 beat 每天低频触发，分批处理避免长事务。
    """
    stats = {"purged": 0, "errors": []}
    try:
        with Session(engine) as session:
            retention_days = _get_retention_days(session=session)
            before = datetime.now(UTC) - timedelta(days=retention_days)
            while True:
                purged = purge_old_transactions(
                    session=session,
                    before=before,
                    limit=WALLET_PURGE_BATCH_LIMIT,
                )
                stats["purged"] += purged
                if purged < WALLET_PURGE_BATCH_LIMIT:
                    break
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append(str(exc))
        logger.exception("钱包流水数据清理异常")
    return stats


def _get_retention_days(*, session: Session) -> int:
    """读取全局设置的钱包流水保留天数，非法值回退默认 7 天。"""
    try:
        days = int(
            get_setting(
                session=session,
                key=WALLET_TRANSACTION_RETENTION_DAYS,
            )
        )
    except (TypeError, ValueError):
        days = DEFAULT_WALLET_RETENTION_DAYS
    return max(1, days)
