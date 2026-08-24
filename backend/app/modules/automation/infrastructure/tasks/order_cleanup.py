"""自动化模块：已完成订单数据定期清理 Celery 任务"""

import logging
from datetime import timedelta

from celery import shared_task
from sqlmodel import Session

from app.core.db import engine
from app.core.time import get_datetime_cn
from app.modules.order.repositories.order import purge_completed_orders
from app.modules.setting.application.setting_query import get_setting
from app.modules.setting.domain.constants import ORDER_RETENTION_DAYS

logger = logging.getLogger(__name__)

# 订单清理批次上限
ORDER_PURGE_BATCH_LIMIT = 500

# 保留期默认值（天），由全局设置 order_retention_days 覆盖
DEFAULT_ORDER_RETENTION_DAYS = 7


@shared_task(
    ignore_result=False,
    name="app.modules.automation.infrastructure.tasks.cleanup_completed_orders",
)
def cleanup_completed_orders() -> dict:
    """定期清理已完成订单数据：物理删除超过保留期的终态订单及其参数。

    保留天数由全局设置 `order_retention_days` 控制，默认 7 天；
    仅清理终态订单（已完成/已退单/已退款），钱包流水不在删除范围；
    由 beat 每天低频触发，分批处理避免长事务。
    """
    stats = {"purged": 0, "errors": []}
    try:
        with Session(engine) as session:
            retention_days = _get_retention_days(session=session)
            before = get_datetime_cn() - timedelta(days=retention_days)
            while True:
                purged = purge_completed_orders(
                    session=session,
                    before=before,
                    limit=ORDER_PURGE_BATCH_LIMIT,
                )
                stats["purged"] += purged
                if purged < ORDER_PURGE_BATCH_LIMIT:
                    break
    except Exception as exc:  # noqa: BLE001
        stats["errors"].append(str(exc))
        logger.exception("已完成订单数据清理异常")
    return stats


def _get_retention_days(*, session: Session) -> int:
    """读取全局设置的订单保留天数，非法值回退默认 7 天。"""
    try:
        days = int(get_setting(session=session, key=ORDER_RETENTION_DAYS))
    except (TypeError, ValueError):
        days = DEFAULT_ORDER_RETENTION_DAYS
    return max(1, days)
