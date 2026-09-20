"""Socket.IO 服务端：连接鉴权、房间命名与在线状态生命周期

只负责实时传输基础设施：

- `connect` / `disconnect`：握手鉴权、绑定用户房间、维护在线状态并广播变化；
- `presence.heartbeat`：客户端心跳，续期在线状态 TTL；
- 房间命名（`user:` / `chat:` / `presence:`）与加入房间的原语。

业务事件（聊天消息、已读、typing、通知等）由业务模块自行注册 Socket.IO 处理器，
并通过 `realtime.publisher` 发布，本模块不感知任何业务语义。
"""

import logging
import uuid
from collections.abc import Mapping

import socketio
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.redis import get_redis_url
from app.modules.realtime.auth import authenticate_token
from app.modules.realtime.events import RealtimeEvent
from app.modules.realtime.manager import (
    add_connection,
    get_user_by_sid,
    has_local_connections,
    mark_offline,
    mark_online,
    refresh_heartbeat,
    remove_connection,
)

logger = logging.getLogger(__name__)

USER_ROOM_PREFIX = "user:"
CHAT_ROOM_PREFIX = "chat:"
PRESENCE_ROOM_PREFIX = "presence:"


def user_room(user_id: uuid.UUID | str) -> str:
    """用户私有房间：定点推送与该用户强相关的提醒（通知、未读数等）"""
    return f"{USER_ROOM_PREFIX}{user_id}"


def chat_room(chat_id: uuid.UUID | str) -> str:
    """聊天房间：该聊天内的事件（新消息、typing、已读）发给已订阅的参与者"""
    return f"{CHAT_ROOM_PREFIX}{chat_id}"


def presence_room(user_id: uuid.UUID | str) -> str:
    """在线状态房间：订阅某个用户在线状态变化的连接"""
    return f"{PRESENCE_ROOM_PREFIX}{user_id}"


sio = socketio.AsyncServer(
    async_mode="asgi",
    # CORS 由 FastAPI 应用的 CORSMiddleware 统一处理；
    # 若此处再配置，engineio 与中间件会各写一份 Access-Control-Allow-Origin，
    # 导致 polling 传输被浏览器以“重复 CORS 头”拦截，实时通道无法建立
    cors_allowed_origins=[],
    transports=["websocket", "polling"],
    client_manager=socketio.AsyncRedisManager(
        get_redis_url(settings.REDIS_SOCKETIO_DB),
    ),
)


async def _broadcast_presence(user_id: uuid.UUID, *, is_online: bool) -> None:
    """向订阅该用户在线状态的连接广播变化（best-effort）"""
    await sio.emit(
        RealtimeEvent.PRESENCE_CHANGED,
        {"user_id": str(user_id), "is_online": is_online},
        to=presence_room(user_id),
    )


@sio.event
async def connect(sid: str, _environ: Mapping, auth: Mapping | None) -> None:
    """握手鉴权：token 有效则绑定用户房间，否则拒绝连接"""
    token = (auth or {}).get("token") if isinstance(auth, Mapping) else None
    # 鉴权是同步实现（JWT 解析 + 数据库查询），放到线程池避免阻塞事件循环
    user = await run_in_threadpool(authenticate_token, token) if token else None
    if user is None or user.id is None:
        raise socketio.exceptions.ConnectionRefusedError("unauthorized")
    add_connection(user.id, sid)
    await sio.enter_room(sid, user_room(user.id))
    became_online = await mark_online(user.id, sid)
    if became_online:
        await _broadcast_presence(user.id, is_online=True)
    logger.info("socket connected sid=%s user=%s", sid, user.id)


@sio.event
async def disconnect(sid: str) -> None:
    """连接断开：清理本进程绑定，最后一个连接消失时广播离线"""
    user_id = remove_connection(sid)
    if user_id is None:
        return
    went_offline = await mark_offline(user_id, sid)
    # 本进程仍有该用户的其他连接时不可能离线（多设备 / 标签页快速重连）
    if went_offline and not has_local_connections(user_id):
        await _broadcast_presence(user_id, is_online=False)
    logger.info("socket disconnected sid=%s user=%s", sid, user_id)


@sio.on(RealtimeEvent.PRESENCE_HEARTBEAT)
async def presence_heartbeat(sid: str, _data: Mapping | None = None) -> None:
    """客户端心跳：续期在线状态 TTL（无绑定的连接直接忽略）"""
    user_id = get_user_by_sid(sid)
    if user_id is None:
        return
    await refresh_heartbeat(user_id, sid)
