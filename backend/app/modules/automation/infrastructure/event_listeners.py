"""自动化模块：事件监听器（注册到全局 EventBus）"""

import logging

from app.core.event_bus import listen
from app.modules.automation.application.event import dispatch_event
from app.modules.automation.models import AutomationEvent

logger = logging.getLogger(__name__)


@listen("*")
def handle_automation_event(event: AutomationEvent) -> None:
    """按启用的 AutomationRule 为事件生成自动化任务。"""
    created = dispatch_event(event=event)
    if created:
        logger.info(
            "事件 %s 生成 %d 个自动化任务",
            event.event_type,
            len(created),
        )
