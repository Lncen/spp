"""自动化模块：失败或中断事件补发 Celery 任务。"""

import logging

from celery import shared_task
from sqlmodel import Session

from app.core.db import engine
from app.core.time import get_datetime_cn
from app.modules.automation.application.event import dispatch_event
from app.modules.automation.repositories.event import (
    claim_events_for_redispatch,
)

logger = logging.getLogger(__name__)

REDISPATCH_BATCH_LIMIT = 100


@shared_task(
    ignore_result=False,
    name=(
        "app.modules.automation.infrastructure.tasks."
        "redispatch_stale_automation_events"
    ),
)
def redispatch_stale_automation_events() -> dict:
    """扫描并补发长期未完成或失败的自动化事件。"""
    now = get_datetime_cn()
    with Session(engine) as session:
        events = claim_events_for_redispatch(
            session=session,
            now=now,
            limit=REDISPATCH_BATCH_LIMIT,
        )

    dispatched = 0
    errors: list[str] = []
    for event in events:
        try:
            dispatch_event(event=event)
            dispatched += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            logger.warning(
                "自动化事件补发失败 event_id=%s: %s",
                event.id,
                exc,
            )

    return {
        "claimed": len(events),
        "dispatched": dispatched,
        "errors": errors,
    }
