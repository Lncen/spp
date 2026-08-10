"""自动化模块：自动化事件查询应用服务"""

from sqlalchemy.orm import Session

from app.modules.automation.repositories.event import (
    count_events,
    list_events,
)
from app.modules.automation.schemas import (
    AutomationEventPublic,
    AutomationEventsPublic,
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
