"""聊天模块：Socket.IO 事件接入

客户端 → 服务端：`chat.subscribe` / `chat.unsubscribe` / `chat.message.send` /
`chat.typing` / `chat.read`

服务端 → 客户端：

| 事件 | 房间 | 说明 |
| --- | --- | --- |
| `chat.message.created` | `chat:{chat_id}` | 新消息（先落库后广播） |
| `chat.message.read` | `chat:{chat_id}` | 某成员已读到哪里 |
| `chat.typing` | 参与者 `user:{id}` | 输入中状态，只发给其他参与者，不落库 |
| `chat.unread.updated` | `user:{id}` | 该用户某条聊天的未读数变化 |

约定：

- 处理器运行在 Socket.IO 主事件循环线程内，数据库与权限查询一律 `run_in_threadpool`；
- 消息**先提交 PostgreSQL 再发布实时事件**，实时失败不影响消息事实；
- 每个事件独立限流，超限直接丢弃（不报错，避免刷屏放大）。
"""

import asyncio
import logging
import uuid
from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from app.core.db import engine
from app.modules.chat.application.access import get_accessible_chat
from app.modules.chat.application.message_manage import (
    send_chat_message,
    to_message_items,
)
from app.modules.chat.application.read_manage import mark_chat_read
from app.modules.chat.domain.constants import ChatRealtimeEvent
from app.modules.chat.infrastructure import presence, rate_limit
from app.modules.chat.repositories.participant import (
    count_unread_for_chat,
    list_participant_user_ids,
)
from app.modules.chat.schemas.message import MessageCreate
from app.modules.realtime.manager import get_user_by_sid
from app.modules.realtime.publisher import (
    publish_to_room_async,
    publish_to_user_async,
)
from app.modules.realtime.server import chat_room, sio
from app.modules.user.models import User

logger = logging.getLogger(__name__)


@sio.on(ChatRealtimeEvent.SUBSCRIBE)
async def chat_subscribe(sid: str, data: Mapping | None) -> None:
    """订阅聊天：校验访问权后加入 `chat:{chat_id}` 与参与者 presence 房间"""
    user_id = get_user_by_sid(sid)
    chat_id = _parse_uuid(data, "chat_id")
    if user_id is None or chat_id is None:
        return
    if not await rate_limit.allow_event(
        event=ChatRealtimeEvent.SUBSCRIBE, user_id=user_id
    ):
        return
    participant_ids = await run_in_threadpool(
        _load_participant_ids, user_id, chat_id
    )
    if participant_ids is None:
        return
    await sio.enter_room(sid, chat_room(chat_id))
    await presence.subscribe_chat_presence(
        sid=sid, observer_id=user_id, participant_ids=participant_ids
    )


@sio.on(ChatRealtimeEvent.UNSUBSCRIBE)
async def chat_unsubscribe(sid: str, data: Mapping | None) -> None:
    """取消订阅：离开聊天房间与参与者 presence 房间"""
    user_id = get_user_by_sid(sid)
    chat_id = _parse_uuid(data, "chat_id")
    if user_id is None or chat_id is None:
        return
    participant_ids = await run_in_threadpool(
        _load_participant_ids, user_id, chat_id
    )
    await sio.leave_room(sid, chat_room(chat_id))
    if participant_ids is not None:
        await presence.unsubscribe_chat_presence(
            sid=sid, observer_id=user_id, participant_ids=participant_ids
        )


@sio.on(ChatRealtimeEvent.MESSAGE_SEND)
async def chat_message_send(sid: str, data: Mapping | None) -> None:
    """发送消息：先落库，再向聊天房间广播并向其他参与者推送未读数"""
    user_id = get_user_by_sid(sid)
    chat_id = _parse_uuid(data, "chat_id")
    if user_id is None or chat_id is None:
        return
    if not await rate_limit.allow_event(
        event=ChatRealtimeEvent.MESSAGE_SEND, user_id=user_id
    ):
        return
    payload = _parse_message(data)
    if payload is None:
        return
    sent = await run_in_threadpool(
        _send_message, user_id, chat_id, payload
    )
    if sent is None:
        return
    message_payload, unread_counts = sent
    await publish_to_room_async(
        chat_room(chat_id),
        ChatRealtimeEvent.MESSAGE_CREATED,
        message_payload,
    )
    if unread_counts:
        # 未读推送同时携带消息摘要：接收方不一定订阅了该聊天房间，
        # 提醒（Toast / 提示音 / 系统通知）挂在这条一定送达的事件上
        preview = (
            message_payload["file_name"]
            if message_payload["message_type"] == "FILE"
            else message_payload["content"]
        )
        await asyncio.gather(
            *(
                publish_to_user_async(
                    recipient_id,
                    ChatRealtimeEvent.UNREAD_UPDATED,
                    {
                        "chat_id": str(chat_id),
                        "unread_count": unread_count,
                        "message_id": message_payload["id"],
                        "sender_id": message_payload["sender_id"],
                        "sender_name": message_payload["sender_name"],
                        "message_type": message_payload["message_type"],
                        "preview": preview,
                    },
                )
                for recipient_id, unread_count in unread_counts.items()
            )
        )


@sio.on(ChatRealtimeEvent.TYPING)
async def chat_typing(sid: str, data: Mapping | None) -> None:
    """输入中状态：不落库，只发给该聊天的其他参与者"""
    user_id = get_user_by_sid(sid)
    chat_id = _parse_uuid(data, "chat_id")
    if user_id is None or chat_id is None:
        return
    if not await rate_limit.allow_event(
        event=ChatRealtimeEvent.TYPING, user_id=user_id
    ):
        return
    participant_ids = await run_in_threadpool(
        _load_participant_ids, user_id, chat_id
    )
    if participant_ids is None:
        return
    is_typing = True if data is None else bool(data.get("is_typing", True))
    recipients = [
        participant_id
        for participant_id in participant_ids
        if participant_id != user_id
    ]
    if not recipients:
        return
    payload = {
        "chat_id": str(chat_id),
        "user_id": str(user_id),
        "is_typing": is_typing,
    }
    await asyncio.gather(
        *(
            publish_to_user_async(
                recipient_id, ChatRealtimeEvent.TYPING, payload
            )
            for recipient_id in recipients
        )
    )


@sio.on(ChatRealtimeEvent.READ)
async def chat_read(sid: str, data: Mapping | None) -> None:
    """标记已读：推进游标后广播已读位置并回推自己的未读数"""
    user_id = get_user_by_sid(sid)
    chat_id = _parse_uuid(data, "chat_id")
    message_id = _parse_uuid(data, "message_id")
    if user_id is None or chat_id is None or message_id is None:
        return
    if not await rate_limit.allow_event(
        event=ChatRealtimeEvent.READ, user_id=user_id
    ):
        return
    result = await run_in_threadpool(
        _mark_read, user_id, chat_id, message_id
    )
    if result is None:
        return
    payload = {
        "chat_id": str(chat_id),
        "user_id": str(user_id),
        "message_id": str(message_id),
        "last_read_message_id": result["last_read_message_id"],
        "unread_count": result["unread_count"],
    }
    await publish_to_room_async(
        chat_room(chat_id), ChatRealtimeEvent.MESSAGE_READ, payload
    )
    await publish_to_user_async(
        user_id,
        ChatRealtimeEvent.UNREAD_UPDATED,
        {
            "chat_id": str(chat_id),
            "unread_count": result["unread_count"],
        },
    )


def _parse_uuid(data: Mapping | None, key: str) -> uuid.UUID | None:
    """从载荷里解析 UUID 字段（缺失或非法返回 None）"""
    if not isinstance(data, Mapping):
        return None
    raw = data.get(key)
    if raw is None:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


def _parse_message(data: Mapping | None) -> MessageCreate | None:
    """解析发送消息载荷（校验失败视为无效事件，直接丢弃）"""
    if not isinstance(data, Mapping):
        return None
    try:
        return MessageCreate.model_validate(dict(data))
    except ValidationError:
        return None


def _load_participant_ids(
    user_id: uuid.UUID, chat_id: uuid.UUID
) -> list[uuid.UUID] | None:
    """校验访问权并返回聊天参与者（无权限返回 None）"""
    with Session(engine) as session:
        user = session.get(User, user_id)
        if user is None:
            return None
        try:
            chat, _ = get_accessible_chat(
                session=session, user=user, chat_id=chat_id
            )
        except HTTPException:
            return None
        return list_participant_user_ids(session=session, chat_id=chat.id)


def _send_message(
    user_id: uuid.UUID,
    chat_id: uuid.UUID,
    payload: MessageCreate,
) -> tuple[dict[str, Any], dict[uuid.UUID, int]] | None:
    """落库并组装实时载荷（无权限或校验失败返回 None）"""
    with Session(engine) as session:
        user = session.get(User, user_id)
        if user is None:
            return None
        try:
            message, recipients = send_chat_message(
                session=session,
                current_user=user,
                chat_id=chat_id,
                payload=payload,
            )
        except HTTPException:
            return None
        message_payload = to_message_items(
            session=session, messages=[message]
        )[0].model_dump(mode="json")
        unread_counts = {
            recipient_id: count_unread_for_chat(
                session=session, chat_id=chat_id, user_id=recipient_id
            )
            for recipient_id in recipients
        }
        return message_payload, unread_counts


def _mark_read(
    user_id: uuid.UUID,
    chat_id: uuid.UUID,
    message_id: uuid.UUID,
) -> dict[str, Any] | None:
    """推进已读游标（无权限返回 None）"""
    with Session(engine) as session:
        user = session.get(User, user_id)
        if user is None:
            return None
        try:
            result = mark_chat_read(
                session=session,
                current_user=user,
                chat_id=chat_id,
                message_id=message_id,
            )
        except HTTPException:
            return None
        return {
            "last_read_message_id": (
                str(result.last_read_message_id)
                if result.last_read_message_id
                else None
            ),
            "unread_count": result.unread_count,
        }
