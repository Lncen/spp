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


def create_event_in_session(
    *,
    session: Session,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> AutomationEvent:
    """在调用方事务内创建事件记录，随业务事务一起提交（不立即分发）。

    用于与业务数据同事务落库的场景（如订单创建），事件不因提交后发布失败而丢失；
    事务提交后需调用 dispatch_event 分发监听器。
    """
    return create_event(
        session=session,
        event_type=event_type,
        payload=payload or {},
    )


def dispatch_event(event: AutomationEvent) -> None:
    """分发事件给监听器（事件须已随业务事务提交）。

    单个监听器失败不影响其他监听器，仅记录日志；
    事件记录已在库中，可追溯并按需补发。
    """
    for listener in _listeners_for(event.event_type):
        try:
            listener(event)
        except Exception:  # noqa: BLE001
            logger.exception(
                "事件监听器执行失败 event_type=%s event_id=%s",
                event.event_type,
                event.id,
            )


def publish(
    *,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> AutomationEvent:
    """发布业务事件：独立事务落库（审计）后，再同步分发监听器。

    当前可使用的事件类型：

    - ``order.paid``：订单创建成功（已付款），payload 含 ``order_id``；
    - ``order.fulfillment_failed``：订单履约异常，payload 含 ``order_id`` / ``order_no`` / ``remark``。

    另可通过 automation 模块接口（POST /automation/events，超管权限）发布任意自定义事件类型；
    新增业务事件时请同步补充本备注。
    """
    with Session(engine) as session:
        event = create_event_in_session(
            session=session,
            event_type=event_type,
            payload=payload,
        )
        session.commit()
        session.refresh(event)
    dispatch_event(event)
    return event


def _listeners_for(event_type: str) -> list[Listener]:
    """获取事件监听器：全局监听器优先，其次按事件类型匹配。"""
    return [*LISTENERS.get("*", []), *LISTENERS.get(event_type, [])]
