"""Socket.IO 服务端：连接管理、用户房间绑定、实时事件接入 Redis"""

import logging
import uuid
from collections.abc import Callable, Mapping

import socketio

from app.core.config import settings
from app.core.redis import get_redis_url
from app.modules.realtime.auth import authenticate_token
from app.modules.realtime.events import RealtimeEvent
from app.modules.realtime.manager import (
    add_connection,
    get_user_by_sid,
    remove_connection,
    set_offline,
    set_online,
)

logger = logging.getLogger(__name__)

USER_ROOM_PREFIX = "user:"

# 会话参与者回调（依赖倒置）：业务模块注册后，Socket.IO 才具备会话级校验能力
ConversationParticipantsFn = Callable[
    [uuid.UUID, uuid.UUID], list[uuid.UUID] | None
]
_conversation_participants_fns: list[ConversationParticipantsFn] = []


def register_conversation_participants(
    fn: ConversationParticipantsFn,
) -> None:
    """注册「会话参与者」查询回调（客服模块在启动时调用）"""
    _conversation_participants_fns.append(fn)


def user_room(user_id: uuid.UUID | str) -> str:
    """用户私有房间名，用于定向推送"""
    return f"{USER_ROOM_PREFIX}{user_id}"


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


@sio.event
async def connect(sid: str, _environ: Mapping, auth: Mapping | None) -> None:
    """握手鉴权：token 有效则绑定用户房间，否则拒绝连接"""
    token = (auth or {}).get("token") if isinstance(auth, Mapping) else None
    user = authenticate_token(token) if token else None
    if user is None or user.id is None:
        raise socketio.exceptions.ConnectionRefusedError("unauthorized")
    add_connection(user.id, sid)
    await sio.enter_room(sid, user_room(user.id))
    await set_online(user.id, sid)
    await sio.emit(
        RealtimeEvent.SYSTEM_CONNECTED,
        {"user_id": str(user.id)},
        to=user_room(user.id),
    )
    logger.info("socket connected sid=%s user=%s", sid, user.id)


@sio.event
async def disconnect(sid: str) -> None:
    """连接断开：清理绑定并广播在线状态变化"""
    user_id = remove_connection(sid)
    if user_id is not None:
        await set_offline(user_id, sid)
        await sio.emit(
            RealtimeEvent.SYSTEM_DISCONNECTED,
            {"user_id": str(user_id)},
            to=user_room(user_id),
        )
        logger.info("socket disconnected sid=%s user=%s", sid, user_id)


@sio.on(RealtimeEvent.CUSTOMER_SERVICE_TYPING)
async def customer_service_typing(sid: str, data: Mapping) -> None:
    """客服输入中：校验会话参与者后向对方推送 typing 事件"""
    user_id = get_user_by_sid(sid)
    if user_id is None:
        return
    try:
        raw_id = data.get("conversation_id") or data.get("conversationId")
        conversation_id = uuid.UUID(str(raw_id))
    except (ValueError, TypeError):
        return
    participant_ids: list[uuid.UUID] | None = None
    for fn in _conversation_participants_fns:
        participant_ids = fn(user_id, conversation_id)
        if participant_ids is not None:
            break
    if not participant_ids:
        return
    payload = {
        "conversation_id": str(conversation_id),
        "user_id": str(user_id),
    }
    for participant_id in participant_ids:
        if participant_id == user_id:
            continue
        await sio.emit(
            RealtimeEvent.CUSTOMER_SERVICE_TYPING,
            payload,
            to=user_room(participant_id),
        )
