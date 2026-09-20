"""通知投递测试：事件幂等、站内即时送达、邮件异步、载荷不外泄"""

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from app.core.config import settings
from app.core.db import engine
from app.modules.automation.models import AutomationEvent
from app.modules.automation.repositories.event import create_event
from app.modules.notification.application import event_listen, realtime_publish
from app.modules.notification.domain.constants import (
    ChannelType,
    DeliveryStatus,
)
from app.modules.notification.models import Notification, NotificationDelivery
from app.modules.notification.repositories.notification import (
    create_notification,
)
from app.modules.user.models import User
from tests.utils.user import create_random_user


def _superuser_recipient_count() -> int:
    """内置规则命中全部超管；用例不假设超管只有一个（其它用例会新建超管）"""
    with Session(engine) as session:
        return len(
            session.exec(
                select(User).where(col(User.is_superuser).is_(True))
            ).all()
        )


def _create_failed_event() -> AutomationEvent:
    """造一条「订单履约异常」事件（内置规则命中超级管理员）"""
    with Session(engine) as session:
        event = create_event(
            session=session,
            event_type="order.fulfillment_failed",
            payload={"order_id": str(uuid.uuid4()), "order_no": "NO-1"},
        )
        session.commit()
        session.refresh(event)
        return event


def _deliveries_for(event_id: uuid.UUID) -> list[NotificationDelivery]:
    """按事件 ID 查询其通知的投递记录"""
    with Session(engine) as session:
        notifications = session.exec(
            select(Notification).where(col(Notification.event_id) == event_id)
        ).all()
        if not notifications:
            return []
        return list(
            session.exec(
                select(NotificationDelivery).where(
                    col(NotificationDelivery.notification_id).in_(
                        [item.id for item in notifications]
                    )
                )
            ).all()
        )


def test_event_is_consumed_once_on_replay(monkeypatch: Any) -> None:
    """事件重放（重试 / 补发）不会重复生成通知与投递记录"""
    enqueued: list[str] = []
    monkeypatch.setattr(
        event_listen,
        "enqueue_delivery",
        lambda delivery_id: enqueued.append(delivery_id) or True,
    )
    event = _create_failed_event()

    event_listen.process_notification_event(event=event)
    event_listen.process_notification_event(event=event)

    with Session(engine) as session:
        notifications = session.exec(
            select(Notification).where(col(Notification.event_id) == event.id)
        ).all()
    expected = _superuser_recipient_count()
    assert len(notifications) == expected
    assert {
        notification.dedupe_key for notification in notifications
    } == {
        f"{event.id}:order_fulfillment_failed:{notification.user_id}"
        for notification in notifications
    }

    deliveries = _deliveries_for(event.id)
    in_app = [item for item in deliveries if item.channel == ChannelType.IN_APP]
    email = [item for item in deliveries if item.channel == ChannelType.EMAIL]
    # 站内通知落库即送达，不进入异步投递
    assert len(in_app) == expected
    assert all(item.status == DeliveryStatus.SENT for item in in_app)
    assert all(item.sent_at is not None for item in in_app)
    # 邮件保持 pending，由 Celery 异步发送
    assert len(email) == expected
    assert all(item.status == DeliveryStatus.PENDING for item in email)
    assert sorted(enqueued) == sorted(str(item.id) for item in email)


def test_realtime_payload_excludes_internal_snapshot(
    db: Session,
    monkeypatch: Any,
) -> None:
    """实时推送只带用户需要的信息，不暴露内部事件载荷快照"""
    captured: list[dict[str, Any]] = []

    def _capture(
        user_id: uuid.UUID, event: str, data: dict[str, Any]
    ) -> bool:
        captured.append({"user_id": user_id, "event": event, "data": data})
        return True

    monkeypatch.setattr(realtime_publish, "publish_to_user", _capture)
    user = create_random_user(db)
    notification = create_notification(
        session=db,
        event_id=None,
        event_type="manual",
        rule_id=None,
        user_id=user.id,
        email_to=user.email,
        title="标题",
        content="内容",
        template_name=None,
        payload={"secret": "内部载荷"},
    )
    db.commit()
    db.refresh(notification)

    assert realtime_publish.publish_notification_created(notification) is True

    assert len(captured) == 1
    payload = captured[0]["data"]
    assert set(payload) == {
        "id",
        "title",
        "content",
        "event_type",
        "created_at",
    }
    assert captured[0]["event"] == "notification.created"


def test_user_notification_api_hides_snapshot(
    client: TestClient,
    db: Session,
) -> None:
    """用户通知接口不返回 payload_snapshot（仅管理端保留）"""
    user = create_random_user(db)
    notification = create_notification(
        session=db,
        event_id=None,
        event_type="manual",
        rule_id=None,
        user_id=user.id,
        email_to=user.email,
        title="仅站内",
        content="正文",
        template_name=None,
        payload={"secret": "内部载荷"},
    )
    db.commit()
    db.refresh(notification)
    headers = _login(client, db, user)

    response = client.get(f"{settings.API_V1_STR}/notifications/", headers=headers)

    assert response.status_code == 200, response.text
    items = {
        item["id"]: item for item in response.json()["data"]
    }
    assert str(notification.id) in items
    assert "payload_snapshot" not in items[str(notification.id)]


def test_manual_send_delivers_in_app_and_enqueues_email(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch: Any,
) -> None:
    """管理端手动发送：站内即时送达，邮件异步投递"""
    enqueued: list[str] = []
    monkeypatch.setattr(
        "app.modules.notification.application.notification_admin.enqueue_delivery",
        lambda delivery_id: enqueued.append(delivery_id) or True,
    )
    target = create_random_user(db)

    response = client.post(
        f"{settings.API_V1_STR}/notifications/admin",
        headers=superuser_token_headers,
        json={
            "title": "手动通知",
            "content": "正文",
            "channels": [ChannelType.IN_APP, ChannelType.EMAIL],
            "user_ids": [str(target.id)],
        },
    )

    assert response.status_code == 200, response.text
    assert "站内 1 条已送达" in response.json()["message"]
    assert "邮件 1 条进入异步投递" in response.json()["message"]
    with Session(engine) as session:
        deliveries = session.exec(
            select(NotificationDelivery)
            .join(
                Notification,
                col(NotificationDelivery.notification_id) == col(Notification.id),
            )
            .where(col(Notification.user_id) == target.id)
        ).all()
    by_channel = {delivery.channel: delivery for delivery in deliveries}
    assert by_channel[ChannelType.IN_APP].status == DeliveryStatus.SENT
    assert by_channel[ChannelType.EMAIL].status == DeliveryStatus.PENDING
    assert enqueued == [str(by_channel[ChannelType.EMAIL].id)]


def _login(
    client: TestClient, db: Session, user: User
) -> dict[str, str]:
    """登录测试用户，返回认证头"""
    from tests.utils.user import authentication_token_from_email

    return authentication_token_from_email(
        client=client, email=user.email, db=db
    )
