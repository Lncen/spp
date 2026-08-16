"""系统日志事件监听器（挂载到全局 EventBus）"""

import logging

from app.core.event_bus import listen
from app.modules.automation.models import AutomationEvent
from app.modules.system_log.application.event_listen import (
    process_system_log_event,
)

logger = logging.getLogger(__name__)


@listen("*")  # type: ignore[untyped-decorator]
def handle_system_log_event(event: AutomationEvent) -> None:
    """将每个业务事件写入系统日志，日志失败不向上抛出"""
    try:
        process_system_log_event(event=event)
    except Exception:  # noqa: BLE001
        logger.exception(
            "系统日志写入失败 event_type=%s event_id=%s",
            event.event_type,
            event.id,
        )
