"""自动化模块：事件路由"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, get_current_active_superuser
from app.modules.automation.application.event_publish import (
    publish_automation_event,
)
from app.modules.automation.application.event_query import (
    list_automation_events,
)
from app.modules.automation.schemas import (
    AutomationEventCreate,
    AutomationEventPublic,
    AutomationEventsPublic,
)

router = APIRouter(prefix="/automation/events", tags=["automation"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AutomationEventsPublic,
)
def read_automation_events(
    session: SessionDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    event_type: str | None = Query(default=None, title="事件类型过滤"),
) -> Any:
    """获取自动化事件列表（超管权限）"""
    return list_automation_events(
        session=session,
        skip=skip,
        limit=limit,
        event_type=event_type,
    )


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AutomationEventPublic,
)
def publish_automation_event_route(
    *,
    event_in: AutomationEventCreate,
) -> Any:
    """手动发布业务事件并触发规则分发（超管权限）"""
    return publish_automation_event(event_in=event_in)
