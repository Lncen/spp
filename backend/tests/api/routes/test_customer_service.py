"""客服模块：会话 / 消息 / 实时发布测试"""

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.modules.customer_service.application import realtime_publish
from app.modules.user.application.user_query import get_user_by_email
from tests.utils.user import authentication_token_from_email, create_random_user
from tests.utils.utils import random_email, random_lower_string


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


def _create_agent_headers(
    *,
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> dict[str, str]:
    """创建一个持有客服接待权限的普通用户，返回其认证头"""
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
        json={"permission_ids": [permission_ids["customer_service:view"]]},
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
    return headers


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
    """非超管持有 customer_service:view 即为客服坐席：可查看全部会话并以管理端身份回复"""
    user_headers, _ = _create_user_headers(client, db)
    conversation_id = _create_my_conversation(client, user_headers)

    agent_headers = _create_agent_headers(
        client=client,
        db=db,
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
        json={"content": "客服坐席回复"},
    )
    assert reply.status_code == 200
    assert reply.json()["sender_role"] == "admin"


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

    # 管理员回复 -> 用户会话未读 +1
    client.post(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=superuser_token_headers,
        json={"content": "在的"},
    )
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
    assert forbidden.status_code == 403

    forbidden_send = client.post(
        f"{settings.API_V1_STR}/customer-service/conversations/"
        f"{conversation_id}/messages",
        headers=other_headers,
        json={"content": "越权消息"},
    )
    assert forbidden_send.status_code == 403


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
