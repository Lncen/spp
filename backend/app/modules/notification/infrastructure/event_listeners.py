"""通知中心：事件监听器（挂载到全局 EventBus）"""

import logging

from app.core.event_bus import listen
from app.modules.automation.models import AutomationEvent
from app.modules.notification.application.event_listen import (
    process_notification_event,
)

logger = logging.getLogger(__name__)


@listen("*")  # type: ignore[untyped-decorator]
def handle_notification_event(event: AutomationEvent) -> None:
    """按通知规则为业务事件生成通知（未命中规则时静默跳过）"""
    process_notification_event(event=event)
