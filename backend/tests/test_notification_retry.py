"""通知事件消费重试测试：失败可重试、成功幂等、退避未到不重试"""

import uuid
from datetime import timedelta
from typing import Any

from sqlmodel import Session, col, select

from app.core.db import engine
from app.core.time import get_datetime_cn
from app.modules.automation.infrastructure.tasks.notification_retry import (
    retry_notification_consumptions,
)
from app.modules.automation.models import AutomationEvent
from app.modules.automation.repositories.event import create_event
from app.modules.notification.application import event_listen
from app.modules.notification.domain.constants import ConsumptionStatus
from app.modules.notification.models import (
    Notification,
    NotificationEventConsumption,
)
from app.modules.notification.repositories.consumption import get_consumption
from app.modules.user.models import User


def _superuser_recipient_count() -> int:
    """内置规则命中全部超管；用例不假设超管只有一个（其它用例会新建超管）"""
    with Session(engine) as session:
        return len(
            session.exec(
                select(User).where(col(User.is_superuser).is_(True))
            ).all()
        )


def _create_failed_event() -> AutomationEvent:
    """造一条命中内置规则的事件（接收人为超级管理员）"""
    with Session(engine) as session:
        event = create_event(
            session=session,
            event_type="order.fulfillment_failed",
            payload={"order_id": str(uuid.uuid4()), "order_no": "NO-RETRY"},
        )
        session.commit()
        session.refresh(event)
        return event


def _load_consumption(event_id: uuid.UUID) -> NotificationEventConsumption:
    """读取消费状态"""
    with Session(engine) as session:
        consumption = get_consumption(session=session, event_id=event_id)
        assert consumption is not None
        return consumption


def _make_retry_due(event_id: uuid.UUID) -> None:
    """把退避时间改到过去，便于直接验证重试任务"""
    with Session(engine) as session:
        consumption = get_consumption(session=session, event_id=event_id)
        assert consumption is not None
        consumption.next_retry_at = get_datetime_cn() - timedelta(minutes=1)
        session.add(consumption)
        session.commit()


def _notifications_for(event_id: uuid.UUID) -> list[Notification]:
    """查询事件生成的通知"""
    with Session(engine) as session:
        return list(
            session.exec(
                select(Notification).where(col(Notification.event_id) == event_id)
            ).all()
        )


def test_failed_consumption_is_retried_and_idempotent(
    monkeypatch: Any,
) -> None:
    """消费失败会记录状态并退避重试，重试成功后只产生一条通知"""
    enqueued: list[str] = []
    monkeypatch.setattr(
        event_listen,
        "enqueue_delivery",
        lambda delivery_id: enqueued.append(delivery_id) or True,
    )
    real_create = event_listen._create_notifications
    calls = {"count": 0}

    def flaky_create(**kwargs: Any) -> None:
        """第一次消费抛错，模拟消费端故障"""
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("消费失败")
        real_create(**kwargs)

    monkeypatch.setattr(event_listen, "_create_notifications", flaky_create)
    event = _create_failed_event()

    event_listen.process_notification_event(event=event)

    consumption = _load_consumption(event.id)
    assert consumption.status == ConsumptionStatus.FAILED
    assert consumption.attempt_count == 1
    assert consumption.last_error == "消费失败"
    assert consumption.next_retry_at is not None
    assert _notifications_for(event.id) == []

    # 退避时间未到：重试任务不会捞起该事件
    assert retry_notification_consumptions() == {"claimed": 0, "processed": 0}

    _make_retry_due(event.id)
    assert retry_notification_consumptions() == {"claimed": 1, "processed": 1}

    consumption = _load_consumption(event.id)
    assert consumption.status == ConsumptionStatus.DONE
    assert consumption.attempt_count == 2
    assert consumption.next_retry_at is None
    expected = _superuser_recipient_count()
    assert len(_notifications_for(event.id)) == expected
    assert len(enqueued) == expected


def test_done_consumption_is_not_reprocessed(monkeypatch: Any) -> None:
    """已成功消费的事件再次分发（重放）时直接跳过"""
    enqueued: list[str] = []
    monkeypatch.setattr(
        event_listen,
        "enqueue_delivery",
        lambda delivery_id: enqueued.append(delivery_id) or True,
    )
    event = _create_failed_event()

    event_listen.process_notification_event(event=event)
    event_listen.process_notification_event(event=event)

    consumption = _load_consumption(event.id)
    assert consumption.status == ConsumptionStatus.DONE
    assert consumption.attempt_count == 1
    expected = _superuser_recipient_count()
    assert len(_notifications_for(event.id)) == expected
    assert len(enqueued) == expected


def test_retry_skips_future_backoff() -> None:
    """退避时间在未来的失败记录不会被重试任务认领"""
    event = _create_failed_event()
    with Session(engine) as session:
        session.add(
            NotificationEventConsumption(
                event_id=event.id,
                status=ConsumptionStatus.FAILED,
                attempt_count=1,
                next_retry_at=get_datetime_cn() + timedelta(hours=1),
                last_error="稍后重试",
            )
        )
        session.commit()

    assert retry_notification_consumptions() == {"claimed": 0, "processed": 0}
    assert _load_consumption(event.id).status == ConsumptionStatus.FAILED
