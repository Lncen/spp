"""自动化模块：通知事件消费重试任务

通知消费挂在全局 EventBus 上，EventBus 只保证尽力分发（监听器失败只记日志，
自动化事件补发也不会重跑 EventBus 监听器）。因此通知消费自己记录状态：

```text
失败 / worker 中断 → 本任务重新消费 → dedupe_key 保证不重复 → 最终成功
```
"""

import logging
from datetime import timedelta

from celery import shared_task
from sqlmodel import Session, col, select

from app.core.db import engine
from app.core.time import get_datetime_cn
from app.modules.automation.models import AutomationEvent
from app.modules.notification.domain.constants import CONSUMPTION_STALE_MINUTES
from app.modules.notification.repositories.consumption import (
    claim_due_consumptions,
)

logger = logging.getLogger(__name__)

RETRY_BATCH_LIMIT = 100


@shared_task(
    ignore_result=False,
    name=(
        "app.modules.automation.infrastructure.tasks."
        "retry_notification_consumptions"
    ),
)
def retry_notification_consumptions() -> dict:
    """重新消费未完成的通知事件（失败重试，重复消费由幂等键兜底）"""
    # 局部导入：通知应用服务在模块级导入本包（入队邮件投递），
    # 在函数内导入可避免 tasks 包与 notification 应用服务之间的循环依赖
    from app.modules.notification.application.event_listen import (
        process_notification_event,
    )

    now = get_datetime_cn()
    with Session(engine) as session:
        event_ids = claim_due_consumptions(
            session=session,
            now=now,
            stale_cutoff=now - timedelta(minutes=CONSUMPTION_STALE_MINUTES),
            limit=RETRY_BATCH_LIMIT,
        )
        if not event_ids:
            return {"claimed": 0, "processed": 0}
        events = session.exec(
            select(AutomationEvent).where(
                col(AutomationEvent.id).in_(event_ids)
            )
        ).all()

    processed = 0
    for event in events:
        process_notification_event(event=event)
        processed += 1
    logger.info(
        "通知事件重试完成 claimed=%d processed=%d", len(event_ids), processed
    )
    return {"claimed": len(event_ids), "processed": processed}
