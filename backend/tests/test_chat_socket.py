"""聊天 Socket.IO 事件测试：订阅、发送、typing、已读与限流

直接调用事件处理器协程（不建立真实 WebSocket），
用真实 PostgreSQL 校验落库结果、用替身记录实时发布与房间操作。
"""

import asyncio
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.redis import get_redis, run_redis_sync
from app.modules.chat.domain.constants import ChatRealtimeEvent
from app.modules.chat.infrastructure import rate_limit
from app.modules.chat.infrastructure import socket as chat_socket
from app.modules.chat.models import Message
from app.modules.realtime import manager as realtime_manager
from app.modules.realtime.server import chat_room, presence_room
from app.modules.user.models import User
from tests.utils.user import (
    authentication_token_from_email,
    create_random_user,
)

API = f"{settings.API_V1_STR}/chat"


class RealtimeRecorder:
    """记录实时发布与房间操作的替身"""

    def __init__(self) -> None:
        self.room_emits: list[tuple[str, str, dict]] = []
        self.user_emits: list[tuple[uuid.UUID | str, str, dict]] = []
        self.joined_rooms: list[str] = []
        self.left_rooms: list[str] = []

    async def publish_to_room_async(
        self, room: str, event: str, data: dict
    ) -> bool:
        self.room_emits.append((room, event, data))
        return True

    async def publish_to_user_async(
        self, user_id: uuid.UUID | str, event: str, data: dict
    ) -> bool:
        self.user_emits.append((user_id, event, data))
        return True

    async def enter_room(self, sid: str, room: str) -> None:
        self.joined_rooms.append(room)

    async def leave_room(self, sid: str, room: str) -> None:
        self.left_rooms.append(room)


def _patch_realtime(monkeypatch: Any) -> RealtimeRecorder:
    """替换实时出口与房间操作，避免测试依赖真实 Redis / Socket.IO"""
    recorder = RealtimeRecorder()
    monkeypatch.setattr(
        chat_socket, "publish_to_room_async", recorder.publish_to_room_async
    )
    monkeypatch.setattr(
        chat_socket, "publish_to_user_async", recorder.publish_to_user_async
    )
    monkeypatch.setattr(chat_socket.sio, "enter_room", recorder.enter_room)
    monkeypatch.setattr(chat_socket.sio, "leave_room", recorder.leave_room)

    async def _allow(**_: Any) -> bool:
        """限流替身：测试内一律放行"""
        return True

    monkeypatch.setattr(rate_limit, "allow_event", _allow)
    return recorder


def _create_user(client: TestClient, db: Session) -> tuple[dict[str, str], User]:
    user = create_random_user(db)
    headers = authentication_token_from_email(
        client=client, email=user.email, db=db
    )
    return headers, user


def _create_direct_chat_id(
    client: TestClient,
    headers: dict[str, str],
    other_user_id: uuid.UUID,
) -> uuid.UUID:
    response = client.post(
        f"{API}/direct",
        headers=headers,
        json={"user_id": str(other_user_id)},
    )
    assert response.status_code == 200, response.text
    return uuid.UUID(response.json()["id"])


def test_subscribe_joins_chat_and_presence_rooms(
    client: TestClient,
    db: Session,
    monkeypatch: Any,
) -> None:
    """订阅聊天后加入聊天房间与参与者在线状态房间"""
    recorder = _patch_realtime(monkeypatch)
    headers_a, user_a = _create_user(client, db)
    _headers_b, user_b = _create_user(client, db)
    chat_id = _create_direct_chat_id(client, headers_a, user_b.id)
    sid = f"sid-{uuid.uuid4()}"
    realtime_manager.add_connection(user_a.id, sid)
    try:
        asyncio.run(
            chat_socket.chat_subscribe(sid, {"chat_id": str(chat_id)})
        )
    finally:
        realtime_manager.remove_connection(sid)

    assert recorder.joined_rooms[0] == chat_room(chat_id)
    assert set(recorder.joined_rooms[1:]) == {
        presence_room(user_a.id),
        presence_room(user_b.id),
    }


def test_subscribe_rejects_non_participant(
    client: TestClient,
    db: Session,
    monkeypatch: Any,
) -> None:
    """非参与者订阅不会加入任何房间"""
    recorder = _patch_realtime(monkeypatch)
    headers_a, user_a = _create_user(client, db)
    _headers_b, user_b = _create_user(client, db)
    _headers_c, user_c = _create_user(client, db)
    chat_id = _create_direct_chat_id(client, headers_a, user_b.id)
    sid = f"sid-{uuid.uuid4()}"
    realtime_manager.add_connection(user_c.id, sid)
    try:
        asyncio.run(
            chat_socket.chat_subscribe(sid, {"chat_id": str(chat_id)})
        )
    finally:
        realtime_manager.remove_connection(sid)

    assert recorder.joined_rooms == []


def test_message_send_persists_then_broadcasts(
    client: TestClient,
    db: Session,
    monkeypatch: Any,
) -> None:
    """发送消息：先落库，再向聊天房间广播并对接收人推送未读数"""
    recorder = _patch_realtime(monkeypatch)
    headers_a, user_a = _create_user(client, db)
    _headers_b, user_b = _create_user(client, db)
    chat_id = _create_direct_chat_id(client, headers_a, user_b.id)
    sid = f"sid-{uuid.uuid4()}"
    realtime_manager.add_connection(user_a.id, sid)
    try:
        asyncio.run(
            chat_socket.chat_message_send(
                sid,
                {
                    "chat_id": str(chat_id),
                    "content": "实时消息",
                    "client_message_id": "socket-1",
                },
            )
        )
    finally:
        realtime_manager.remove_connection(sid)

    db.expire_all()
    messages = db.exec(
        select(Message).where(col(Message.chat_id) == chat_id)
    ).all()
    assert len(messages) == 1
    assert messages[0].content == "实时消息"

    room_event, room_name, payload = recorder.room_emits[0]
    assert room_name == ChatRealtimeEvent.MESSAGE_CREATED
    assert room_event == chat_room(chat_id)
    assert payload["content"] == "实时消息"
    assert payload["id"] == str(messages[0].id)

    unread_events = [
        item
        for item in recorder.user_emits
        if item[1] == ChatRealtimeEvent.UNREAD_UPDATED
    ]
    assert len(unread_events) == 1
    recipient_id, event, unread_payload = unread_events[0]
    assert recipient_id == user_b.id
    assert event == ChatRealtimeEvent.UNREAD_UPDATED
    assert unread_payload["chat_id"] == str(chat_id)
    assert unread_payload["unread_count"] == 1
    # 未读推送同时携带消息摘要：接收方即使没订阅该聊天也能给出提醒
    assert unread_payload["message_id"] == str(messages[0].id)
    assert unread_payload["sender_id"] == str(user_a.id)
    assert unread_payload["preview"] == "实时消息"
    assert unread_payload["message_type"] == "TEXT"


def test_message_send_is_idempotent_on_socket(
    client: TestClient,
    db: Session,
    monkeypatch: Any,
) -> None:
    """同一 client_message_id 通过 socket 重复发送只落一条消息"""
    _patch_realtime(monkeypatch)
    headers_a, user_a = _create_user(client, db)
    _headers_b, user_b = _create_user(client, db)
    chat_id = _create_direct_chat_id(client, headers_a, user_b.id)
    sid = f"sid-{uuid.uuid4()}"
    realtime_manager.add_connection(user_a.id, sid)
    payload = {
        "chat_id": str(chat_id),
        "content": "重复发送",
        "client_message_id": "socket-retry",
    }
    try:
        for _ in range(5):
            asyncio.run(chat_socket.chat_message_send(sid, payload))
    finally:
        realtime_manager.remove_connection(sid)

    db.expire_all()
    assert (
        len(
            db.exec(
                select(Message).where(col(Message.chat_id) == chat_id)
            ).all()
        )
        == 1
    )


def test_typing_goes_only_to_other_participants(
    client: TestClient,
    db: Session,
    monkeypatch: Any,
) -> None:
    """typing 不落库，只发给其他参与者"""
    recorder = _patch_realtime(monkeypatch)
    headers_a, user_a = _create_user(client, db)
    _headers_b, user_b = _create_user(client, db)
    chat_id = _create_direct_chat_id(client, headers_a, user_b.id)
    sid = f"sid-{uuid.uuid4()}"
    realtime_manager.add_connection(user_a.id, sid)
    try:
        asyncio.run(
            chat_socket.chat_typing(
                sid, {"chat_id": str(chat_id), "is_typing": True}
            )
        )
    finally:
        realtime_manager.remove_connection(sid)

    assert recorder.user_emits == [
        (
            user_b.id,
            ChatRealtimeEvent.TYPING,
            {
                "chat_id": str(chat_id),
                "user_id": str(user_a.id),
                "is_typing": True,
            },
        )
    ]
    db.expire_all()
    assert (
        db.exec(select(Message).where(col(Message.chat_id) == chat_id)).all()
        == []
    )


def test_message_persists_when_realtime_publish_fails(
    client: TestClient,
    db: Session,
    monkeypatch: Any,
) -> None:
    """实时通道故障（Redis 不可用）时消息仍然落库：实时只是提醒"""
    recorder = _patch_realtime(monkeypatch)

    async def _publish_failed(*_: Any, **__: Any) -> bool:
        """模拟发布失败：publisher 自身吞掉异常并返回 False"""
        return False

    monkeypatch.setattr(chat_socket, "publish_to_room_async", _publish_failed)
    headers_a, user_a = _create_user(client, db)
    _headers_b, user_b = _create_user(client, db)
    chat_id = _create_direct_chat_id(client, headers_a, user_b.id)
    sid = f"sid-{uuid.uuid4()}"
    realtime_manager.add_connection(user_a.id, sid)
    try:
        asyncio.run(
            chat_socket.chat_message_send(
                sid,
                {"chat_id": str(chat_id), "content": "Redis 故障时的消息"},
            )
        )
    finally:
        realtime_manager.remove_connection(sid)

    assert recorder.room_emits == []
    db.expire_all()
    messages = db.exec(
        select(Message).where(col(Message.chat_id) == chat_id)
    ).all()
    assert [message.content for message in messages] == ["Redis 故障时的消息"]


def test_read_event_advances_cursor_and_notifies(
    client: TestClient,
    db: Session,
    monkeypatch: Any,
) -> None:
    """已读事件：推进游标、广播已读位置、回推未读数"""
    recorder = _patch_realtime(monkeypatch)
    headers_a, user_a = _create_user(client, db)
    headers_b, user_b = _create_user(client, db)
    chat_id = _create_direct_chat_id(client, headers_a, user_b.id)
    sid_a = f"sid-{uuid.uuid4()}"
    realtime_manager.add_connection(user_a.id, sid_a)
    try:
        asyncio.run(
            chat_socket.chat_message_send(
                sid_a,
                {"chat_id": str(chat_id), "content": "待读消息"},
            )
        )
    finally:
        realtime_manager.remove_connection(sid_a)
    db.expire_all()
    message = db.exec(
        select(Message).where(col(Message.chat_id) == chat_id)
    ).one()

    sid_b = f"sid-{uuid.uuid4()}"
    realtime_manager.add_connection(user_b.id, sid_b)
    recorder.room_emits.clear()
    recorder.user_emits.clear()
    try:
        asyncio.run(
            chat_socket.chat_read(
                sid_b,
                {"chat_id": str(chat_id), "message_id": str(message.id)},
            )
        )
    finally:
        realtime_manager.remove_connection(sid_b)

    assert recorder.room_emits == [
        (
            chat_room(chat_id),
            ChatRealtimeEvent.MESSAGE_READ,
            {
                "chat_id": str(chat_id),
                "user_id": str(user_b.id),
                "message_id": str(message.id),
                "last_read_message_id": str(message.id),
                "unread_count": 0,
            },
        )
    ]
    assert recorder.user_emits == [
        (
            user_b.id,
            ChatRealtimeEvent.UNREAD_UPDATED,
            {"chat_id": str(chat_id), "unread_count": 0},
        )
    ]


@pytest.mark.usefixtures("client")
def test_rate_limit_blocks_after_quota() -> None:
    """限流按事件独立计数：超出配额后拒绝，直到窗口过期"""
    user_id = uuid.uuid4()
    key = f"chat:ratelimit:{ChatRealtimeEvent.TYPING}:{user_id}"
    try:
        allowed = [
            run_redis_sync(
                rate_limit.allow_event(
                    event=ChatRealtimeEvent.TYPING, user_id=user_id
                )
            )
            for _ in range(11)
        ]
        # 配额 10 次 / 秒
        assert allowed[:10] == [True] * 10
        assert allowed[10] is False
        # 其他事件的配额独立
        assert run_redis_sync(
            rate_limit.allow_event(
                event=ChatRealtimeEvent.MESSAGE_SEND, user_id=user_id
            )
        )
    finally:
        run_redis_sync(get_redis().delete(key))


@pytest.mark.usefixtures("client")
def test_rate_limit_fails_open_when_redis_unavailable(
    monkeypatch: Any,
) -> None:
    """Redis 不可用时放行，不因为限流组件故障让用户发不出消息"""

    def _boom() -> None:
        raise RuntimeError("redis down")

    monkeypatch.setattr(rate_limit, "get_redis", _boom)

    assert run_redis_sync(
        rate_limit.allow_event(
            event=ChatRealtimeEvent.MESSAGE_SEND, user_id=uuid.uuid4()
        )
    )
