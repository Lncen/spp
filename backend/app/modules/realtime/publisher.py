"""实时事件发布：业务模块统一实时出口（best-effort，跨进程经 Redis Pub/Sub）

分两个明确入口，避免在同一事件循环里同步等待自己调度的协程：

- 同步入口 `publish_to_user` / `publish_to_users` / `publish_to_room`：
  使用 `write_only` 的 `RedisManager`，可在 Celery worker、事件总线监听器、
  FastAPI 同步路由（线程池）中直接调用；
- 异步入口 `publish_to_user_async` / `publish_to_users_async` / `publish_to_room_async`：
  使用 `AsyncRedisManager`，供 async 路由与 Socket.IO 事件处理器调用。

两者都只向 Socket.IO 的 Redis 通道写入消息（与各 Web 进程订阅的通道一致），
因此不再需要后台事件循环，也不需要在发布器里持有 Socket.IO 服务实例。
"""

import asyncio
import logging
import uuid
from collections.abc import Iterable
from typing import Any

import socketio
from socketio.async_redis_manager import AsyncRedisManager

from app.core.config import settings
from app.core.redis import get_redis_url
from app.modules.realtime.server import user_room

logger = logging.getLogger(__name__)

_sync_manager: socketio.RedisManager | None = None
_async_manager: AsyncRedisManager | None = None


def _get_sync_manager() -> socketio.RedisManager:
    """获取（惰性创建）仅写的同步发布器"""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = socketio.RedisManager(
            get_redis_url(settings.REDIS_SOCKETIO_DB),
            write_only=True,
        )
    return _sync_manager


def _get_async_manager() -> AsyncRedisManager:
    """获取（惰性创建）仅写的异步发布器"""
    global _async_manager
    if _async_manager is None:
        _async_manager = AsyncRedisManager(
            get_redis_url(settings.REDIS_SOCKETIO_DB),
            write_only=True,
        )
    return _async_manager


async def publish_to_room_async(
    room: str,
    event: str,
    data: dict[str, Any],
) -> bool:
    """异步向指定 room 发布实时事件"""
    try:
        await _get_async_manager().emit(event, data, to=room)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("实时事件发布失败 room=%s event=%s", room, event)
        return False


async def publish_to_user_async(
    user_id: uuid.UUID | str,
    event: str,
    data: dict[str, Any],
) -> bool:
    """异步向单个用户发布实时事件"""
    return await publish_to_room_async(user_room(user_id), event, data)


async def publish_to_users_async(
    user_ids: Iterable[uuid.UUID | str],
    event: str,
    data: dict[str, Any],
) -> int:
    """并发向多个用户发布实时事件，返回成功发布数"""
    rooms = [user_room(user_id) for user_id in user_ids]
    if not rooms:
        return 0
    results = await asyncio.gather(
        *(publish_to_room_async(room, event, data) for room in rooms)
    )
    return sum(1 for result in results if result)


def publish_to_room(room: str, event: str, data: dict[str, Any]) -> bool:
    """同步向指定 room 发布实时事件（best-effort）"""
    try:
        _get_sync_manager().emit(event, data, to=room)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("实时事件发布失败 room=%s event=%s", room, event)
        return False


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
    return sum(
        1 for user_id in user_ids if publish_to_user(user_id, event, data)
    )
