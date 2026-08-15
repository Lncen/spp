"""实时事件发布：业务模块统一实时出口（best-effort，跨进程经 Redis Pub/Sub）

Web 进程在启动时通过 init_publisher 绑定 Socket.IO 服务与主事件循环；
Celery worker 等无主循环进程惰性创建 write_only 的 Redis manager 实例
（只写不订阅），保证任意进程都能向实时通道发布事件。
"""

import asyncio
import logging
import threading
import uuid
from collections.abc import Awaitable, Iterable
from typing import Any

import socketio

from app.core.config import settings
from app.core.redis import get_redis_url
from app.modules.realtime.events import RealtimeEvent  # noqa: F401  供调用方复用事件名
from app.modules.realtime.server import sio as _server_sio
from app.modules.realtime.server import user_room

logger = logging.getLogger(__name__)

_server: socketio.AsyncServer | None = None
_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None


def init_publisher() -> None:
    """应用启动时绑定 Web 进程的 Socket.IO 服务与主事件循环"""
    global _server, _loop
    _server = _server_sio
    _loop = asyncio.get_running_loop()


def _ensure_publisher() -> tuple[socketio.AsyncServer, asyncio.AbstractEventLoop]:
    """获取发布器实例；惰性创建仅写的发布器与后台事件循环（Celery worker 场景）"""
    global _server, _loop, _loop_thread
    if _server is None:
        _server = socketio.AsyncServer(
            async_mode="asgi",
            client_manager=socketio.AsyncRedisManager(
                get_redis_url(settings.REDIS_SOCKETIO_DB),
                write_only=True,
            ),
        )
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(
            target=_loop.run_forever,
            daemon=True,
            name="realtime-publisher-loop",
        )
        _loop_thread.start()
    return _server, _loop


def _run_sync[T](awaitable: Awaitable[T], *, timeout: float = 2.0) -> T | None:
    """在同步上下文执行异步发布，失败仅记日志不抛出"""
    _, loop = _ensure_publisher()
    try:
        future = asyncio.run_coroutine_threadsafe(awaitable, loop)
        return future.result(timeout=timeout)
    except Exception:  # noqa: BLE001
        logger.exception("实时事件发布失败")
        return None


async def publish_to_room_async(
    room: str,
    event: str,
    data: dict[str, Any],
) -> bool:
    """异步向指定 room 发布实时事件"""
    server, _ = _ensure_publisher()
    try:
        await server.emit(event, data, to=room)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("实时事件发布失败 room=%s event=%s", room, event)
        return False


def publish_to_room(room: str, event: str, data: dict[str, Any]) -> bool:
    """同步向指定 room 发布实时事件（best-effort）"""
    result = _run_sync(publish_to_room_async(room, event, data))
    return result is not None and result


def publish_to_user(
    user_id: uuid.UUID | str,
    event: str,
    data: dict[str, Any],
) -> bool:
    """向单个用户发布实时事件"""
    return publish_to_room(user_room(user_id), event, data)


def publish_to_users(
    user_ids: Iterable[uuid.UUID | str],
    event: str,
    data: dict[str, Any],
) -> int:
    """向多个用户发布实时事件，返回成功发布数"""
    count = 0
    for user_id in user_ids:
        if publish_to_user(user_id, event, data):
            count += 1
    return count
