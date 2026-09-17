"""自动化模块：事件应用服务

按业务能力归组：事件发布、事件查询与按规则分发（生成自动化任务）。
"""

from datetime import timedelta

from sqlmodel import Session

from app.core.db import engine
from app.core.event_bus import publish as publish_event
from app.core.time import get_datetime_cn
from app.modules.automation.domain.constants import AutomationEventStatus
from app.modules.automation.domain.validation import validate_rule_config
from app.modules.automation.models import AutomationEvent, AutomationTask
from app.modules.automation.repositories.event import (
    count_events,
    list_events,
)
from app.modules.automation.repositories.rule import (
    list_enabled_rules_by_event,
)
from app.modules.automation.repositories.task import create_task
from app.modules.automation.schemas import (
    AutomationEventCreate,
    AutomationEventPublic,
    AutomationEventsPublic,
)

MAX_ERROR_LENGTH = 2000
BASE_REDISPATCH_DELAY_SECONDS = 60
MAX_REDISPATCH_DELAY_SECONDS = 3600


def publish_automation_event(
    *,
    event_in: AutomationEventCreate,
) -> AutomationEvent:
    """发布业务事件：落库并触发规则分发。"""
    return publish_event(
        event_type=event_in.event_type,
        payload=event_in.payload,
    )


def list_automation_events(
    *,
    session: Session,
    skip: int,
    limit: int,
    event_type: str | None,
) -> AutomationEventsPublic:
    """分页获取自动化事件列表。"""
    count = count_events(session=session, event_type=event_type)
    events = list_events(
        session=session,
        skip=skip,
        limit=limit,
        event_type=event_type,
    )
    return AutomationEventsPublic(
        data=[AutomationEventPublic.model_validate(event) for event in events],
        count=count,
    )


def dispatch_event(*, event: AutomationEvent) -> list[AutomationTask]:
    """按事件类型查找启用的规则，为每条规则创建一个自动化任务，并推进事件分发状态。"""
    with Session(engine) as session:
        db_event = session.get(AutomationEvent, event.id)
        if db_event is None:
            return []
        db_event.status = AutomationEventStatus.DISPATCHING
        db_event.processing_at = get_datetime_cn()
        try:
            rules = list_enabled_rules_by_event(
                session=session,
                event_type=db_event.event_type,
            )
            tasks = []
            for rule in rules:
                validate_rule_config(rule.config)
                config = dict(rule.config)
                task_options = config.pop("task_options", {}) or {}
                payload = {**db_event.payload, **config}
                delay_seconds = int(task_options.get("delay_seconds", 0) or 0)
                execute_at = (
                    get_datetime_cn() + timedelta(seconds=delay_seconds)
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
            db_event.dispatched_at = get_datetime_cn()
            db_event.last_error = None
            db_event.next_dispatch_at = None
            session.commit()
            for task in tasks:
                session.refresh(task)
            return tasks
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            db_event.status = AutomationEventStatus.FAILED
            db_event.dispatch_attempts += 1
            db_event.last_error = str(exc)[:MAX_ERROR_LENGTH]
            retry_delay = min(
                MAX_REDISPATCH_DELAY_SECONDS,
                BASE_REDISPATCH_DELAY_SECONDS
                * (2 ** max(0, db_event.dispatch_attempts - 1)),
            )
            db_event.next_dispatch_at = get_datetime_cn() + timedelta(
                seconds=retry_delay
            )
            session.add(db_event)
            session.commit()
            raise
