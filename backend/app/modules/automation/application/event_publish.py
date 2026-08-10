"""自动化模块：事件发布应用服务"""

from app.core.event_bus import publish as publish_event
from app.modules.automation.models import AutomationEvent
from app.modules.automation.schemas import AutomationEventCreate


def publish_automation_event(
    *,
    event_in: AutomationEventCreate,
) -> AutomationEvent:
    """发布业务事件：落库并触发规则分发。"""
    return publish_event(
        event_type=event_in.event_type,
        payload=event_in.payload,
    )
