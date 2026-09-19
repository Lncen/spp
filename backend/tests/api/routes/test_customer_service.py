"""客服模块：会话 / 消息 / 实时发布测试"""

import threading
import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.db import engine
from app.core.time import get_datetime_cn
from app.init_models_data.roles import DEFAULT_USER_ROLE_CODE
from app.modules.automation.infrastructure.tasks import cleanup_conversations
from app.modules.customer_service.application import realtime_publish
from app.modules.customer_service.application.conversation_manage import (
    get_or_create_conversation,
)
from app.modules.customer_service.domain.constants import SenderRole
from app.modules.customer_service.models import Conversation, ConversationMessage
from app.modules.customer_service.repositories.conversation import (
    purge_old_conversations,
)
from app.modules.customer_service.repositories.message import create_message
from app.modules.user.application.user_query import get_user_by_email
from tests.utils.user import authentication_token_from_email, create_random_user
from tests.utils.utils import random_email, random_lower_string

# 会话清理测试使用的保留期（天），与全局设置默认值一致
CONVERSATION_RETENTION_TEST_DAYS = 7


def _create_user_headers(client: TestClient, db: Session) -> tuple[dict[str, str], object]:
    """创建随机用户并返回认证头与用户对象"""
    user = create_random_user(db)
    headers = authentication_token_from_email(
        client=client, email=user.email, db=db
    )
    return headers, user


def _create_my_conversation(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations",
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()["id"]


def _remove_user_roles(
    *,
    client: TestClient,
    user_id: uuid.UUID,
    superuser_token_headers: dict[str, str],
) -> None:
    """移除用户的全部角色，用于验证权限被撤销后的行为"""
    roles = client.get(
        f"{settings.API_V1_STR}/users/{user_id}/roles",
        headers=superuser_token_headers,
    )
    assert roles.status_code == 200, roles.text
    for role in roles.json()["data"]:
        removed = client.delete(
            f"{settings.API_V1_STR}/users/{user_id}/roles/{role['id']}",
            headers=superuser_token_headers,
        )
        assert removed.status_code == 200, removed.text


def _remove_role_by_code(
    *,
    client: TestClient,
    user_id: uuid.UUID,
    code: str,
    superuser_token_headers: dict[str, str],
) -> None:
    """按角色码移除用户的某个角色（例如内置「普通用户」）"""
    roles = client.get(
        f"{settings.API_V1_STR}/users/{user_id}/roles",
        headers=superuser_token_headers,
    )
    assert roles.status_code == 200, roles.text
    for role in roles.json()["data"]:
        if role["code"] != code:
            continue
        removed = client.delete(
            f"{settings.API_V1_STR}/users/{user_id}/roles/{role['id']}",
            headers=superuser_token_headers,
        )
        assert removed.status_code == 200, removed.text


def _create_agent_headers(
    *,
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    codes: tuple[str, ...] = ("conversation:view",),
) -> tuple[dict[str, str], object]:
    """创建一个持有指定会话权限码的普通用户，返回其认证头与用户对象"""
    listed = client.get(
        f"{settings.API_V1_STR}/permissions", headers=superuser_token_headers
    )
    assert listed.status_code == 200, listed.text
    permission_ids = {
        item["code"]: item["id"] for item in listed.json()["data"]
    }

    role = client.post(
        f"{settings.API_V1_STR}/roles",
        headers=superuser_token_headers,
        json={"code": f"agent_{random_lower_string()}", "name": "客服坐席"},
    )
    assert role.status_code == 200, role.text
    role_id = role.json()["id"]

    granted = client.put(
        f"{settings.API_V1_STR}/roles/{role_id}/permissions",
        headers=superuser_token_headers,
        json={"permission_ids": [permission_ids[code] for code in codes]},
    )
    assert granted.status_code == 200, granted.text

    email = random_email()
    headers = authentication_token_from_email(client=client, email=email, db=db)
    user = get_user_by_email(session=db, email=email)
    assert user is not None and user.id is not None
    assigned = client.post(
        f"{settings.API_V1_STR}/users/{user.id}/roles",
        headers=superuser_token_headers,
        json={"role_id": role_id},
    )
    assert assigned.status_code == 200, assigned.text
    return headers, user


def _create_conversation(session: Session) -> uuid.UUID:
    """创建随机用户的会话（不带消息），返回会话 ID"""
    user = create_random_user(session)
    assert user.id is not None
    return get_or_create_conversation(session=session, user_id=user.id).id


def _create_conversation_with_message(
    *, session: Session, content: str
) -> tuple[uuid.UUID, uuid.UUID]:
    """创建随机用户的会话并写入一条用户消息，返回 (会话 ID, 消息 ID)"""
    user = create_random_user(session)
    assert user.id is not None
    conversation = get_or_create_conversation(session=session, user_id=user.id)
    message = create_message(
        session=session,
        conversation_id=conversation.id,
        sender_id=user.id,
        sender_role=SenderRole.USER,
        content=content,
    )
    session.commit()
    return conversation.id, message.id


def _backdate_conversation(
    *,
    session: Session,
    conversation_id: uuid.UUID,
    days: int,
    clear_last_message_at: bool = False,
) -> None:
    """把会话时间回拨到 N 天前，用于验证清理口径"""
    conversation = session.get(Conversation, conversation_id)
    assert conversation is not None
    old = get_datetime_cn() - timedelta(days=days)
    conversation.created_at = old
    conversation.last_message_at = None if clear_last_message_at else old
    session.add(conversation)
    session.commit()


def _conversation_exists(conversation_id: uuid.UUID) -> bool:
    """新开 Session 查会话是否存在（避免读取当前会话的 identity map 缓存）"""
    with Session(engine) as session:
        return session.get(Conversation, conversation_id) is not None


def _message_exists(message_id: uuid.UUID) -> bool:
    """新开 Session 查消息是否存在"""
    with Session(engine) as session:
        return session.get(ConversationMessage, message_id) is not None


def _purge_leftover_expired(db: Session) -> None:
    """清理历史遗留的超期会话，保证清理用例的断言可重复"""
    purge_old_conversations(
        session=db,
        before=get_datetime_cn() - timedelta(days=CONVERSATION_RETENTION_TEST_DAYS),
        limit=500,
    )


def test_user_get_or_create_conversation(
    client: TestClient,
    db: Session,
) -> None:
    headers, _ = _create_user_headers(client, db)

    first = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations",
        headers=headers,
    )
    assert first.status_code == 200
    conversation_id = first.json()["id"]

    second = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations",
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["id"] == conversation_id


def test_concurrent_get_or_create_conversation_keeps_single_open(
    db: Session,
) -> None:
    """并发发起会话只产生一条进行中会话（用户行锁串行化「先查后插」）"""
    user = create_random_user(db)
    assert user.id is not None
    user_id = user.id

    barrier = threading.Barrier(2)
    created: list[uuid.UUID] = []
    errors: list[Exception] = []

    def worker() -> None:
        try:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                conversation = get_or_create_conversation(
                    session=session, user_id=user_id
                )
                created.append(conversation.id)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors, errors
    assert len(created) == 2
    assert len(set(created)) == 1

    with Session(engine) as session:
        open_count = session.exec(
            select(func.count())
            .select_from(Conversation)
            .where(col(Conversation.user_id) == user_id)
        ).one()
    assert open_count == 1


def test_purge_old_conversations_deletes_expired_with_messages(
    db: Session,
) -> None:
    """清理超期会话：按最后消息时间判定（无消息时按创建时间），消息随会话级联删除"""
    _purge_leftover_expired(db)
    before = get_datetime_cn() - timedelta(days=CONVERSATION_RETENTION_TEST_DAYS)

    recent_id, recent_message_id = _create_conversation_with_message(
        session=db, content="近期消息"
    )
    expired_id, expired_message_id = _create_conversation_with_message(
        session=db, content="超期消息"
    )
    empty_expired_id = _create_conversation(db)

    _backdate_conversation(session=db, conversation_id=expired_id, days=30)
    _backdate_conversation(
        session=db,
        conversation_id=empty_expired_id,
        days=30,
        clear_last_message_at=True,
    )

    purged = purge_old_conversations(session=db, before=before, limit=500)

    assert purged == 2
    assert not _conversation_exists(expired_id)
    assert not _message_exists(expired_message_id)
    assert not _conversation_exists(empty_expired_id)
    assert _conversation_exists(recent_id)
    assert _message_exists(recent_message_id)


def test_purge_old_conversations_respects_batch_limit(db: Session) -> None:
    """清理按批次上限逐批删除，不一次清空"""
    _purge_leftover_expired(db)
    before = get_datetime_cn() - timedelta(days=CONVERSATION_RETENTION_TEST_DAYS)

    expired_ids = [_create_conversation(db) for _ in range(3)]
    for conversation_id in expired_ids:
        _backdate_conversation(session=db, conversation_id=conversation_id, days=30)

    assert purge_old_conversations(session=db, before=before, limit=2) == 2
    assert sum(_conversation_exists(item) for item in expired_ids) == 1

    assert purge_old_conversations(session=db, before=before, limit=2) == 1
    assert sum(_conversation_exists(item) for item in expired_ids) == 0


def test_cleanup_conversations_task_uses_default_retention(
    db: Session,
) -> None:
    """会话清理任务：默认保留期 7 天，删超期会话并保留未超期会话"""
    _purge_leftover_expired(db)
    expired_id = _create_conversation(db)
    kept_id = _create_conversation(db)
    _backdate_conversation(
        session=db,
        conversation_id=expired_id,
        days=CONVERSATION_RETENTION_TEST_DAYS + 1,
    )
    _backdate_conversation(
        session=db,
        conversation_id=kept_id,
        days=CONVERSATION_RETENTION_TEST_DAYS - 1,
    )

    stats = cleanup_conversations()

    assert stats["errors"] == []
    assert not _conversation_exists(expired_id)
    assert _conversation_exists(kept_id)


def test_admin_starts_conversation_for_user(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    _, user = _create_user_headers(client, db)
    assert user.id is not None

    first = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations",
        headers=superuser_token_headers,
        json={"user_id": str(user.id)},
    )
    assert first.status_code == 200
    conversation_id = first.json()["id"]

    # 重复发起返回同一进行中会话
    second = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations",
        headers=superuser_token_headers,
        json={"user_id": str(user.id)},
    )
    assert second.status_code == 200
    assert second.json()["id"] == conversation_id


def test_admin_start_conversation_requires_user_id(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations",
        headers=superuser_token_headers,
        json={},
    )
    assert response.status_code == 400


def test_admin_start_conversation_user_not_found(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations",
        headers=superuser_token_headers,
        json={"user_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


def test_user_sends_message_and_marks_read(
    client: TestClient,
    db: Session,
) -> None:
    headers, _ = _create_user_headers(client, db)
    conversation_id = _create_my_conversation(client, headers)

    sent = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=headers,
        json={"content": "你好，订单发货了吗？"},
    )
    assert sent.status_code == 200
    assert sent.json()["sender_role"] == "user"

    messages = client.get(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=headers,
    )
    assert messages.status_code == 200
    assert messages.json()["count"] == 1
    assert messages.json()["data"][0]["content"] == "你好，订单发货了吗？"

    marked = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/read",
        headers=headers,
    )
    assert marked.status_code == 200


def test_admin_lists_conversations_and_replies(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """超管可查看全部会话，并以管理端身份回复"""
    user_headers, _ = _create_user_headers(client, db)
    conversation_id = _create_my_conversation(client, user_headers)

    listed = client.get(
        f"{settings.API_V1_STR}/customer-service/conversations",
        headers=superuser_token_headers,
    )
    assert listed.status_code == 200
    assert any(
        item["id"] == conversation_id for item in listed.json()["data"]
    )

    reply = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=superuser_token_headers,
        json={"content": "已发货，请注意查收"},
    )
    assert reply.status_code == 200
    assert reply.json()["sender_role"] == "admin"


def test_agent_permission_is_enough_to_receive_all_conversations(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """非超管持有 conversation:view + conversation:reply 即为客服坐席：可查看全部会话并以管理端身份回复"""
    user_headers, _ = _create_user_headers(client, db)
    conversation_id = _create_my_conversation(client, user_headers)

    agent_headers, _agent = _create_agent_headers(
        client=client,
        db=db,
        superuser_token_headers=superuser_token_headers,
        codes=("conversation:view", "conversation:reply"),
    )

    listed = client.get(
        f"{settings.API_V1_STR}/customer-service/conversations",
        headers=agent_headers,
    )
    assert listed.status_code == 200
    assert any(item["id"] == conversation_id for item in listed.json()["data"])

    reply = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=agent_headers,
        json={"content": "客服坐席回复"},
    )
    assert reply.status_code == 200
    assert reply.json()["sender_role"] == "admin"


def test_agent_without_reply_permission_cannot_reply(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """坐席缺少 conversation:reply（去掉内置「普通用户」角色）时，路由层直接拒绝"""
    user_headers, _ = _create_user_headers(client, db)
    conversation_id = _create_my_conversation(client, user_headers)

    agent_headers, agent = _create_agent_headers(
        client=client,
        db=db,
        superuser_token_headers=superuser_token_headers,
    )
    _remove_role_by_code(
        client=client,
        user_id=agent.id,
        code=DEFAULT_USER_ROLE_CODE,
        superuser_token_headers=superuser_token_headers,
    )

    listed = client.get(
        f"{settings.API_V1_STR}/customer-service/conversations",
        headers=agent_headers,
    )
    assert listed.status_code == 200
    assert any(item["id"] == conversation_id for item in listed.json()["data"])

    reply = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=agent_headers,
        json={"content": "只有查看权限的坐席不应发出消息"},
    )
    assert reply.status_code == 400
    assert reply.json()["detail"] == "无回复会话权限"


def test_user_without_agent_permission_lists_only_own_conversations(
    client: TestClient,
    db: Session,
) -> None:
    """未持有客服权限的普通用户，会话列表中看不到他人会话"""
    owner_headers, _ = _create_user_headers(client, db)
    other_headers, _ = _create_user_headers(client, db)
    _create_my_conversation(client, owner_headers)

    listed = client.get(
        f"{settings.API_V1_STR}/customer-service/conversations",
        headers=other_headers,
    )
    assert listed.status_code == 200
    assert listed.json()["data"] == []


def test_user_without_self_view_permission_cannot_access_conversations(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """撤销会话自助权限后，用户连自己的会话都无法访问"""
    headers, user = _create_user_headers(client, db)
    assert user.id is not None
    _remove_user_roles(
        client=client,
        user_id=user.id,
        superuser_token_headers=superuser_token_headers,
    )

    listed = client.get(
        f"{settings.API_V1_STR}/customer-service/conversations",
        headers=headers,
    )
    assert listed.status_code == 400
    assert listed.json()["detail"] == "无会话访问权限"

    created = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations",
        headers=headers,
    )
    assert created.status_code == 400


def test_user_without_reply_permission_cannot_send(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """只有 conversation:self_view 的用户能看自己的会话，但没有回复会话权限发不出消息"""
    headers, user = _create_user_headers(client, db)
    conversation_id = _create_my_conversation(client, headers)
    assert user.id is not None
    _remove_user_roles(
        client=client,
        user_id=user.id,
        superuser_token_headers=superuser_token_headers,
    )

    permissions = client.get(
        f"{settings.API_V1_STR}/permissions", headers=superuser_token_headers
    )
    permission_ids = {
        item["code"]: item["id"] for item in permissions.json()["data"]
    }
    granted = client.put(
        f"{settings.API_V1_STR}/users/{user.id}/permissions",
        headers=superuser_token_headers,
        json={"permission_ids": [permission_ids["conversation:self_view"]]},
    )
    assert granted.status_code == 200, granted.text

    listed = client.get(
        f"{settings.API_V1_STR}/customer-service/conversations",
        headers=headers,
    )
    assert listed.status_code == 200
    assert any(
        item["id"] == conversation_id for item in listed.json()["data"]
    )

    sent = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=headers,
        json={"content": "无自助发送权限"},
    )
    assert sent.status_code == 400
    assert sent.json()["detail"] == "无回复会话权限"


def test_message_send_publishes_realtime(
    client: TestClient,
    db: Session,
    monkeypatch,
) -> None:
    headers, _ = _create_user_headers(client, db)
    conversation_id = _create_my_conversation(client, headers)

    captured: list[tuple] = []

    def fake_publish(user_ids, event, data):
        captured.append((user_ids, event, data))

    monkeypatch.setattr(realtime_publish, "publish_to_users", fake_publish)

    response = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=headers,
        json={"content": "实时事件测试"},
    )
    assert response.status_code == 200
    assert len(captured) == 1
    event, data = captured[0][1], captured[0][2]
    assert event == "customer_service.message.created"
    assert data["conversation_id"] == conversation_id


def test_unread_summary_integrates_notification_and_conversation(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, user = _create_user_headers(client, db)
    assert user.id is not None
    conversation_id = _create_my_conversation(client, headers)

    # 新用户初始总未读为 0
    initial = client.get(
        f"{settings.API_V1_STR}/notifications/unread-summary",
        headers=headers,
    )
    assert initial.status_code == 200
    assert initial.json() == {
        "notification_unread_count": 0,
        "conversation_unread_count": 0,
        "total_unread": 0,
    }

    # 用户发消息 -> 管理端会话未读 +1（管理端累计值可能受其他用例影响，用增量断言）
    before_admin = client.get(
        f"{settings.API_V1_STR}/notifications/unread-summary",
        headers=superuser_token_headers,
    ).json()
    client.post(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=headers,
        json={"content": "在吗"},
    )
    after_admin = client.get(
        f"{settings.API_V1_STR}/notifications/unread-summary",
        headers=superuser_token_headers,
    ).json()
    assert after_admin["conversation_unread_count"] == (
        before_admin["conversation_unread_count"] + 1
    )

    # 管理员回复 -> 用户会话未读 +1（管理员是会话参与者，持有 reply 即可发送）
    replied = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=superuser_token_headers,
        json={"content": "在的"},
    )
    assert replied.status_code == 200
    user_summary = client.get(
        f"{settings.API_V1_STR}/notifications/unread-summary",
        headers=headers,
    ).json()
    assert user_summary["conversation_unread_count"] == 1
    assert user_summary["total_unread"] == 1

    # 管理员给用户发站内通知 -> 用户系统通知未读 +1
    sent = client.post(
        f"{settings.API_V1_STR}/notifications/admin",
        headers=superuser_token_headers,
        json={
            "title": "测试通知",
            "content": "内容",
            "event_type": "manual",
            "user_ids": [str(user.id)],
            "channels": ["in_app"],
            "broadcast": False,
        },
    )
    assert sent.status_code == 200
    user_summary = client.get(
        f"{settings.API_V1_STR}/notifications/unread-summary",
        headers=headers,
    ).json()
    assert user_summary["notification_unread_count"] == 1
    assert user_summary["conversation_unread_count"] == 1
    assert user_summary["total_unread"] == 2

    # 会话已读 + 通知全部已读 -> 总未读归零
    client.post(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/read",
        headers=headers,
    )
    client.post(
        f"{settings.API_V1_STR}/notifications/read-all",
        headers=headers,
    )
    user_summary = client.get(
        f"{settings.API_V1_STR}/notifications/unread-summary",
        headers=headers,
    ).json()
    assert user_summary["total_unread"] == 0


def test_unread_summary_hides_conversations_without_permission(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """未持有会话查看权限时，侧边栏不返回会话未读数（避免暴露会话数据）"""
    # 坐席视角：会话本人发来的消息算作其会话未读
    owner_headers, _owner = _create_user_headers(client, db)
    conversation_id = _create_my_conversation(client, owner_headers)
    sent = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=owner_headers,
        json={"content": "用户消息"},
    )
    assert sent.status_code == 200

    agent_headers, agent = _create_agent_headers(
        client=client,
        db=db,
        superuser_token_headers=superuser_token_headers,
    )
    before = client.get(
        f"{settings.API_V1_STR}/notifications/unread-summary",
        headers=agent_headers,
    )
    assert before.status_code == 200
    assert before.json()["conversation_unread_count"] >= 1

    # 撤销坐席的全部角色（含 conversation:view）后，不再返回会话未读数
    _remove_user_roles(
        client=client,
        user_id=agent.id,
        superuser_token_headers=superuser_token_headers,
    )

    after = client.get(
        f"{settings.API_V1_STR}/notifications/unread-summary",
        headers=agent_headers,
    )
    assert after.status_code == 200
    assert after.json()["conversation_unread_count"] == 0


def test_participant_cannot_access_others_conversation(
    client: TestClient,
    db: Session,
) -> None:
    owner_headers, _ = _create_user_headers(client, db)
    other_headers, _ = _create_user_headers(client, db)
    conversation_id = _create_my_conversation(client, owner_headers)

    forbidden = client.get(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=other_headers,
    )
    assert forbidden.status_code == 400

    forbidden_send = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=other_headers,
        json={"content": "越权消息"},
    )
    assert forbidden_send.status_code == 400


def test_admin_online_status(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    _, user = _create_user_headers(client, db)
    assert user.id is not None

    response = client.get(
        f"{settings.API_V1_STR}/customer-service/online",
        headers=superuser_token_headers,
        params={"user_ids": [str(user.id)]},
    )
    assert response.status_code == 200
    assert str(user.id) in response.json()["online"]


def test_admin_deletes_conversation(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    headers, _ = _create_user_headers(client, db)
    conversation_id = _create_my_conversation(client, headers)

    deleted = client.delete(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}",
        headers=superuser_token_headers,
    )
    assert deleted.status_code == 200

    # 删除后消息接口返回 404
    gone = client.get(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=superuser_token_headers,
    )
    assert gone.status_code == 404


def test_user_cannot_delete_own_conversation(
    client: TestClient,
    db: Session,
) -> None:
    headers, _ = _create_user_headers(client, db)
    conversation_id = _create_my_conversation(client, headers)

    forbidden = client.delete(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}",
        headers=headers,
    )
    assert forbidden.status_code == 403


def test_user_cannot_delete_others_conversation(
    client: TestClient,
    db: Session,
) -> None:
    owner_headers, _ = _create_user_headers(client, db)
    other_headers, _ = _create_user_headers(client, db)
    conversation_id = _create_my_conversation(client, owner_headers)

    forbidden = client.delete(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}",
        headers=other_headers,
    )
    assert forbidden.status_code == 403


def test_delete_conversation_not_found(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
