"""全局进程内事件总线

业务模块通过 publish 发布事件，自动化模块通过 listen 注册监听器并按规则生成任务。
事件先落库（审计与追踪），再同步分发给监听器；单个监听器失败不影响其他监听器。
"""

import logging
from collections.abc import Callable
from typing import Any

from sqlmodel import Session

from app.core.db import engine
from app.modules.automation.models import AutomationEvent
from app.modules.automation.repositories.event import create_event

logger = logging.getLogger(__name__)

Listener = Callable[[AutomationEvent], None]

LISTENERS: dict[str, list[Listener]] = {}


def listen(event_type: str):
    """监听器注册装饰器；event_type="*" 表示监听所有事件。"""

    def decorator(func: Listener) -> Listener:
        LISTENERS.setdefault(event_type, []).append(func)
        return func

    return decorator


def publish(
    *,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> AutomationEvent:
    """发布业务事件：先落库（审计），再同步分发监听器。"""
    with Session(engine) as session:
        event = create_event(
            session=session,
            event_type=event_type,
            payload=payload or {},
        )
        session.commit()
        session.refresh(event)
    for listener in _listeners_for(event_type):
        try:
            listener(event)
        except Exception:  # noqa: BLE001
            logger.exception(
                "事件监听器执行失败 event_type=%s event_id=%s",
                event_type,
                event.id,
            )
    return event


def _listeners_for(event_type: str) -> list[Listener]:
    """获取事件监听器：全局监听器优先，其次按事件类型匹配。"""
    return [*LISTENERS.get("*", []), *LISTENERS.get(event_type, [])]
