"""聊天模块测试：私聊唯一、消息幂等、顺序与游标、未读、群聊与访问控制"""

import uuid
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.time import get_datetime_cn
from app.modules.chat.application import chat_manage
from app.modules.chat.application.message_manage import (
    advance_last_message_if_newer,
    send_chat_message,
)
from app.modules.chat.domain.constants import ChatType, build_direct_key
from app.modules.chat.domain.ordering import is_after
from app.modules.chat.models import Chat, ChatParticipant, Message
from app.modules.chat.repositories.message import count_messages
from app.modules.chat.schemas.message import MessageCreate
from app.modules.user.models import User
from tests.utils.user import authentication_token_from_email, create_random_user

API = f"{settings.API_V1_STR}/chat"


def _create_user(client: TestClient, db: Session) -> tuple[dict[str, str], User]:
    """创建随机用户并返回其认证头与用户对象"""
    user = create_random_user(db)
    headers = authentication_token_from_email(
        client=client, email=user.email, db=db
    )
    return headers, user


def _create_direct_chat(
    client: TestClient,
    headers: dict[str, str],
    other_user_id: uuid.UUID,
) -> dict[str, Any]:
    """通过接口创建私聊并返回聊天数据"""
    response = client.post(
        f"{API}/direct",
        headers=headers,
        json={"user_id": str(other_user_id)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _add_message(
    db: Session,
    *,
    chat_id: uuid.UUID,
    sender_id: uuid.UUID,
    content: str,
    created_at: Any,
) -> Message:
    """直接落一条指定时间的消息（用于构造顺序与并发场景）"""
    message = Message(
        chat_id=chat_id,
        sender_id=sender_id,
        content=content,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def test_domain_direct_key_is_order_independent() -> None:
    """私聊唯一键与用户顺序无关：A→B 与 B→A 得到同一个键"""
    first, second = uuid.uuid4(), uuid.uuid4()

    assert build_direct_key(first, second) == build_direct_key(second, first)
    assert build_direct_key(second, first).startswith(
        str(min(first, second, key=str))
    )


def test_domain_message_order_uses_created_at_then_id() -> None:
    """消息顺序按 `(created_at, id)` 判断，而不是 UUID 主键本身"""
    now = get_datetime_cn()
    earlier = now - timedelta(seconds=1)
    low_id, high_id = sorted([uuid.uuid4(), uuid.uuid4()], key=str)

    assert is_after(
        created_at=now,
        message_id=low_id,
        than_created_at=earlier,
        than_message_id=high_id,
    )
    assert not is_after(
        created_at=earlier,
        message_id=high_id,
        than_created_at=now,
        than_message_id=low_id,
    )
    # 同一时间戳时用 ID 兜底比较，保证游标稳定
    assert is_after(
        created_at=now,
        message_id=high_id,
        than_created_at=now,
        than_message_id=low_id,
    )
    assert not is_after(
        created_at=now,
        message_id=low_id,
        than_created_at=now,
        than_message_id=high_id,
    )


def test_direct_chat_is_shared_by_both_directions(
    client: TestClient, db: Session
) -> None:
    """A→B 与 B→A 命中同一条私聊，数据库里只有一条"""
    headers_a, user_a = _create_user(client, db)
    headers_b, user_b = _create_user(client, db)

    chat_ab = _create_direct_chat(client, headers_a, user_b.id)
    chat_ba = _create_direct_chat(client, headers_b, user_a.id)

    assert chat_ab["id"] == chat_ba["id"]
    direct_key = build_direct_key(user_a.id, user_b.id)
    rows = db.exec(
        select(Chat).where(col(Chat.direct_key) == direct_key)
    ).all()
    assert len(rows) == 1
    participant_ids = {
        row.user_id
        for row in db.exec(
            select(ChatParticipant).where(
                col(ChatParticipant.chat_id) == rows[0].id
            )
        ).all()
    }
    assert participant_ids == {user_a.id, user_b.id}


def test_direct_chat_reuses_row_when_insert_conflicts(
    client: TestClient,
    db: Session,
    monkeypatch: Any,
) -> None:
    """并发创建私聊：插入撞上唯一约束后复用对方已创建的聊天"""
    headers_a, user_a = _create_user(client, db)
    headers_b, user_b = _create_user(client, db)
    existing = _create_direct_chat(client, headers_a, user_b.id)

    real_get_direct_chat = chat_manage.get_direct_chat
    calls = {"count": 0}

    def fake_get_direct_chat(*, session: Session, direct_key: str) -> Any:
        """第一次查询模拟「双方都还没建」的并发窗口"""
        calls["count"] += 1
        if calls["count"] == 1:
            return None
        return real_get_direct_chat(session=session, direct_key=direct_key)

    monkeypatch.setattr(chat_manage, "get_direct_chat", fake_get_direct_chat)

    conflict = client.post(
        f"{API}/direct",
        headers=headers_b,
        json={"user_id": str(user_a.id)},
    )

    assert conflict.status_code == 200, conflict.text
    assert conflict.json()["id"] == existing["id"]
    assert calls["count"] >= 2


def test_client_message_id_is_idempotent(client: TestClient, db: Session) -> None:
    """同一个 client_message_id 重试 10 次只落一条消息"""
    headers_a, user_a = _create_user(client, db)
    _headers_b, user_b = _create_user(client, db)
    chat_id = uuid.UUID(_create_direct_chat(client, headers_a, user_b.id)["id"])
    db.expire_all()
    sender = db.get(User, user_a.id)

    message_ids = set()
    for _ in range(10):
        message, _recipients = send_chat_message(
            session=db,
            current_user=sender,
            chat_id=chat_id,
            payload=MessageCreate(content="重试消息", client_message_id="retry-1"),
        )
        message_ids.add(message.id)

    assert len(message_ids) == 1
    assert count_messages(session=db, chat_id=chat_id) == 1


def test_last_message_never_moves_backwards(client: TestClient, db: Session) -> None:
    """并发发送时旧消息不会覆盖已经推进的 last_message"""
    headers_a, user_a = _create_user(client, db)
    _headers_b, user_b = _create_user(client, db)
    chat_id = uuid.UUID(_create_direct_chat(client, headers_a, user_b.id)["id"])
    sender = db.get(User, user_a.id)

    newest, _ = send_chat_message(
        session=db,
        current_user=sender,
        chat_id=chat_id,
        payload=MessageCreate(content="新消息"),
    )
    db.expire_all()
    chat = db.get(Chat, chat_id)
    assert chat.last_message_id == newest.id

    stale = _add_message(
        db,
        chat_id=chat_id,
        sender_id=user_b.id,
        content="更早的消息",
        created_at=get_datetime_cn() - timedelta(minutes=5),
    )
    moved = advance_last_message_if_newer(
        session=db, chat=chat, message=stale
    )
    db.commit()
    db.expire_all()

    assert moved is False
    assert db.get(Chat, chat_id).last_message_id == newest.id


def test_message_pagination_uses_created_at_and_id(
    client: TestClient, db: Session
) -> None:
    """分页按 `(created_at, id)` 倒序，游标取更早一页且不重不漏"""
    headers_a, user_a = _create_user(client, db)
    _headers_b, user_b = _create_user(client, db)
    chat_id = uuid.UUID(_create_direct_chat(client, headers_a, user_b.id)["id"])
    now = get_datetime_cn()
    oldest = _add_message(
        db,
        chat_id=chat_id,
        sender_id=user_a.id,
        content="第一条",
        created_at=now - timedelta(minutes=2),
    )
    # 两条同一时间戳的消息：由 ID 决定先后
    same_time = now - timedelta(minutes=1)
    tie_one = _add_message(
        db,
        chat_id=chat_id,
        sender_id=user_a.id,
        content="第二条",
        created_at=same_time,
    )
    tie_two = _add_message(
        db,
        chat_id=chat_id,
        sender_id=user_a.id,
        content="第三条",
        created_at=same_time,
    )

    first_page = client.get(
        f"{API}/{chat_id}/messages",
        headers=headers_a,
        params={"limit": 2},
    )
    assert first_page.status_code == 200, first_page.text
    page = first_page.json()
    assert page["count"] == 3
    expected_tie_order = sorted([tie_one.id, tie_two.id], key=str, reverse=True)
    assert [item["id"] for item in page["data"]] == [
        str(expected_tie_order[0]),
        str(expected_tie_order[1]),
    ]

    second_page = client.get(
        f"{API}/{chat_id}/messages",
        headers=headers_a,
        params={"limit": 2, "before": page["data"][-1]["id"]},
    )
    assert second_page.status_code == 200, second_page.text
    assert [item["id"] for item in second_page.json()["data"]] == [str(oldest.id)]


def test_reading_other_chat_cursor_is_rejected(
    client: TestClient, db: Session
) -> None:
    """游标消息不属于该聊天时返回 400"""
    headers_a, user_a = _create_user(client, db)
    headers_c, user_c = _create_user(client, db)
    chat_id = uuid.UUID(_create_direct_chat(client, headers_a, user_c.id)["id"])
    other_headers, other_user = _create_user(client, db)
    other_chat_id = uuid.UUID(
        _create_direct_chat(client, other_headers, user_c.id)["id"]
    )
    foreign = _add_message(
        db,
        chat_id=other_chat_id,
        sender_id=other_user.id,
        content="别的聊天的消息",
        created_at=get_datetime_cn(),
    )

    response = client.get(
        f"{API}/{chat_id}/messages",
        headers=headers_a,
        params={"before": str(foreign.id)},
    )

    assert response.status_code == 400


def test_unread_count_and_read_cursor_only_move_forward(
    client: TestClient, db: Session
) -> None:
    """未读数按游标推算；已读游标只前进，乱序提交不会回退"""
    headers_a, user_a = _create_user(client, db)
    headers_b, user_b = _create_user(client, db)
    chat_id = uuid.UUID(_create_direct_chat(client, headers_a, user_b.id)["id"])
    now = get_datetime_cn()
    older = _add_message(
        db,
        chat_id=chat_id,
        sender_id=user_a.id,
        content="早一点",
        created_at=now - timedelta(minutes=1),
    )
    newer = _add_message(
        db,
        chat_id=chat_id,
        sender_id=user_a.id,
        content="晚一点",
        created_at=now,
    )

    unread = client.get(f"{API}/unread-count", headers=headers_b)
    assert unread.status_code == 200, unread.text
    assert unread.json()["unread_count"] == 2

    mark_newest = client.post(
        f"{API}/{chat_id}/read",
        headers=headers_b,
        json={"message_id": str(newer.id)},
    )
    assert mark_newest.status_code == 200, mark_newest.text
    assert mark_newest.json()["last_read_message_id"] == str(newer.id)
    assert mark_newest.json()["unread_count"] == 0

    # 客户端乱序提交更早的消息：游标不回退
    mark_older = client.post(
        f"{API}/{chat_id}/read",
        headers=headers_b,
        json={"message_id": str(older.id)},
    )
    assert mark_older.status_code == 200, mark_older.text
    assert mark_older.json()["last_read_message_id"] == str(newer.id)
    assert mark_older.json()["unread_count"] == 0


def test_chat_list_shows_display_name_and_unread(
    client: TestClient, db: Session
) -> None:
    """聊天列表带对方展示名与未读数，最后消息冗余跟随发送更新"""
    headers_a, user_a = _create_user(client, db)
    headers_b, user_b = _create_user(client, db)
    chat_id = uuid.UUID(_create_direct_chat(client, headers_a, user_b.id)["id"])
    sender = db.get(User, user_a.id)
    send_chat_message(
        session=db,
        current_user=sender,
        chat_id=chat_id,
        payload=MessageCreate(content="你好"),
    )

    listed = client.get(f"{API}/", headers=headers_b)

    assert listed.status_code == 200, listed.text
    items = listed.json()["data"]
    assert len(items) == 1
    item = items[0]
    assert item["id"] == str(chat_id)
    assert item["type"] == ChatType.DIRECT
    assert item["display_name"] == (user_a.full_name or user_a.username)
    assert item["last_message_preview"] == "你好"
    assert item["unread_count"] == 1


def test_user_cannot_access_other_chat(client: TestClient, db: Session) -> None:
    """非参与者读取他人聊天一律 400，不泄露聊天是否存在之外的信息"""
    headers_a, user_a = _create_user(client, db)
    _headers_b, user_b = _create_user(client, db)
    headers_c, _user_c = _create_user(client, db)
    chat_id = _create_direct_chat(client, headers_a, user_b.id)["id"]

    detail = client.get(f"{API}/{chat_id}", headers=headers_c)
    messages = client.get(f"{API}/{chat_id}/messages", headers=headers_c)
    marked = client.post(
        f"{API}/{chat_id}/read",
        headers=headers_c,
        json={"message_id": str(uuid.uuid4())},
    )

    assert detail.status_code == 400
    assert messages.status_code == 400
    assert marked.status_code == 400


def test_group_chat_requires_permission(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """普通用户不能建群；管理员建群后创建者为群主"""
    headers_user, user = _create_user(client, db)

    denied = client.post(
        f"{API}/group",
        headers=headers_user,
        json={"name": "测试群", "member_ids": []},
    )
    assert denied.status_code == 403

    created = client.post(
        f"{API}/group",
        headers=superuser_token_headers,
        json={"name": "管理员群", "member_ids": [str(user.id)]},
    )
    assert created.status_code == 200, created.text
    chat_id = uuid.UUID(created.json()["id"])
    db.expire_all()
    roles = {
        row.user_id: row.role
        for row in db.exec(
            select(ChatParticipant).where(
                col(ChatParticipant.chat_id) == chat_id
            )
        ).all()
    }
    assert roles[user.id] == "MEMBER"
    assert len([role for role in roles.values() if role == "OWNER"]) == 1


def test_delete_direct_chat_hides_for_self_and_restores(
    client: TestClient, db: Session
) -> None:
    """删除私聊只对自己生效：对方仍可见，对方再发消息或本人重新打开会自动恢复"""
    headers_a, _user_a = _create_user(client, db)
    headers_b, user_b = _create_user(client, db)
    chat_id = _create_direct_chat(client, headers_a, user_b.id)["id"]

    deleted = client.delete(f"{API}/{chat_id}", headers=headers_a)

    assert deleted.status_code == 200, deleted.text
    # 我的列表里没有了，对方仍然可见
    assert all(
        item["id"] != chat_id
        for item in client.get(f"{API}/", headers=headers_a).json()["data"]
    )
    assert any(
        item["id"] == chat_id
        for item in client.get(f"{API}/", headers=headers_b).json()["data"]
    )
    # 对方发来新消息：会话回到我的列表，且只算这一条未读
    db.expire_all()
    sender = db.get(User, user_b.id)
    send_chat_message(
        session=db,
        current_user=sender,
        chat_id=uuid.UUID(chat_id),
        payload=MessageCreate(content="删除后再发一条"),
    )
    restored = client.get(f"{API}/", headers=headers_a).json()["data"]
    restored_chat = next(item for item in restored if item["id"] == chat_id)
    assert restored_chat["unread_count"] == 1
    assert restored_chat["last_message_preview"] == "删除后再发一条"

    # 删除后再由本人打开：自动恢复，且视为已读到最后一条
    assert client.delete(f"{API}/{chat_id}", headers=headers_a).status_code == 200
    opened = client.get(f"{API}/{chat_id}/messages", headers=headers_a)
    assert opened.status_code == 200, opened.text
    reopened = client.get(f"{API}/", headers=headers_a).json()["data"]
    reopened_chat = next(item for item in reopened if item["id"] == chat_id)
    assert reopened_chat["unread_count"] == 0
