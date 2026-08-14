"""自动化模块：事件分发应用服务（按规则生成任务）"""

from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from app.core.db import engine
from app.modules.automation.domain.constants import AutomationEventStatus
from app.modules.automation.models import AutomationEvent, AutomationTask
from app.modules.automation.repositories.rule import (
    list_enabled_rules_by_event,
)
from app.modules.automation.repositories.task import create_task

MAX_ERROR_LENGTH = 2000


def dispatch_event(*, event: AutomationEvent) -> list[AutomationTask]:
    """按事件类型查找启用的规则，为每条规则创建一个自动化任务，并推进事件分发状态。"""
    with Session(engine) as session:
        db_event = session.get(AutomationEvent, event.id)
        if db_event is None:
            return []
        db_event.status = AutomationEventStatus.DISPATCHING
        db_event.processing_at = datetime.now(UTC)
        try:
            rules = list_enabled_rules_by_event(
                session=session,
                event_type=db_event.event_type,
            )
            tasks = []
            for rule in rules:
                config = dict(rule.config)
                task_options = config.pop("task_options", {})
                payload = {**db_event.payload, **config}
                delay_seconds = int(task_options.get("delay_seconds", 0) or 0)
                execute_at = (
                    datetime.now(UTC) + timedelta(seconds=delay_seconds)
                    if delay_seconds > 0
                    else None
                )
                task = create_task(
                    session=session,
                    task_type=rule.action_type,
                    payload=payload,
                    priority=int(task_options.get("priority", 0)),
                    max_retry=int(task_options.get("max_retry", 3)),
                    execute_at=execute_at,
                    event_id=db_event.id,
                    rule_id=rule.id,
                )
                tasks.append(task)
            db_event.status = AutomationEventStatus.DISPATCHED
            db_event.dispatch_attempts += 1
            db_event.dispatched_at = datetime.now(UTC)
            session.commit()
            for task in tasks:
                session.refresh(task)
            return tasks
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            db_event.status = AutomationEventStatus.FAILED
            db_event.dispatch_attempts += 1
            db_event.last_error = str(exc)[:MAX_ERROR_LENGTH]
            session.add(db_event)
            session.commit()
            raise
