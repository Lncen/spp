"""通知中心：事件消费应用服务

监听全局 EventBus 事件 -> 匹配规则 -> 生成 Notification 与 Delivery -> 落库
-> 站内通知直接送达并实时提醒，邮件进入 Celery 异步投递。

同步段只做规则匹配与落库，不执行慢渠道调用。链路是**幂等**的：
同一事件 + 同一规则 + 同一接收人只会生成一条通知（`dedupe_key` 唯一），
因此事件重放、Celery 重试、手动补发都不会重复通知用户。
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.db import engine
from app.core.time import get_datetime_cn
from app.modules.automation.infrastructure.tasks.notification_delivery import (
    enqueue_delivery,
)
from app.modules.automation.models import AutomationEvent
from app.modules.notification.application.realtime_publish import (
    publish_notification_created,
)
from app.modules.notification.domain.constants import (
    CONSUMPTION_BASE_RETRY_SECONDS,
    CONSUMPTION_MAX_ATTEMPTS,
    CONSUMPTION_MAX_RETRY_SECONDS,
    ChannelType,
    ConsumptionStatus,
    DeliveryStatus,
    RecipientRole,
    build_dedupe_key,
)
from app.modules.notification.domain.rules import (
    RecipientsSpec,
    get_rules_for_event,
    render_notification_template,
)
from app.modules.notification.models import (
    Notification,
    NotificationDelivery,
    NotificationEventConsumption,
)
from app.modules.notification.repositories.consumption import get_consumption
from app.modules.notification.repositories.delivery import create_delivery
from app.modules.notification.repositories.notification import (
    create_notification,
    get_notification_by_dedupe_key,
)
from app.modules.user.models import User

logger = logging.getLogger(__name__)

# 幂等键冲突时的重跑次数：并发消费同一事件时，重跑会看到已生成的记录并跳过
_DEDUPE_ATTEMPTS = 2


@dataclass(frozen=True)
class Recipient:
    """解析后的接收人"""

    user_id: uuid.UUID | None
    email: str | None


def process_notification_event(*, event: AutomationEvent) -> None:
    """消费一次事件：登记状态 -> 幂等生成通知 -> 记录成功 / 失败

    失败不会抛出：消费状态记为 `failed` 并写入退避时间，由
    `retry_notification_consumptions` 定时重试，重试期间靠 `dedupe_key` 保证不重复通知。
    """
    rules = get_rules_for_event(event.event_type)
    if not rules:
        return
    if not _begin_consumption(event=event):
        return
    try:
        _consume_event(event=event, rules=rules)
    except Exception as exc:  # noqa: BLE001
        _fail_consumption(event=event, error=str(exc))
        return
    _finish_consumption(event=event)


def _consume_event(*, event: AutomationEvent, rules: list) -> None:
    """带重跑的事件消费：并发撞上幂等唯一约束时重跑一次即收敛"""
    for _ in range(_DEDUPE_ATTEMPTS):
        try:
            _create_notifications(event=event, rules=rules)
            return
        except IntegrityError:
            logger.info("通知事件重复消费，按幂等键重跑 event_id=%s", event.id)
    raise RuntimeError(f"通知事件重复消费冲突未能收敛 event_id={event.id}")


def _begin_consumption(*, event: AutomationEvent) -> bool:
    """登记并进入 processing；已完成或超过重试上限时返回 False"""
    with Session(engine) as session:
        consumption = get_consumption(session=session, event_id=event.id)
        if consumption is None:
            consumption = NotificationEventConsumption(event_id=event.id)
            session.add(consumption)
            session.flush()
        if consumption.status == ConsumptionStatus.DONE:
            return False
        if consumption.attempt_count >= CONSUMPTION_MAX_ATTEMPTS:
            return False
        consumption.status = ConsumptionStatus.PROCESSING
        consumption.attempt_count += 1
        consumption.last_error = None
        consumption.next_retry_at = None
        session.add(consumption)
        session.commit()
        return True


def _finish_consumption(*, event: AutomationEvent) -> None:
    """标记消费成功"""
    with Session(engine) as session:
        consumption = get_consumption(session=session, event_id=event.id)
        if consumption is None:
            return
        consumption.status = ConsumptionStatus.DONE
        consumption.last_error = None
        consumption.next_retry_at = None
        session.add(consumption)
        session.commit()


def _fail_consumption(*, event: AutomationEvent, error: str) -> None:
    """标记消费失败并按指数退避安排下一次重试"""
    with Session(engine) as session:
        consumption = get_consumption(session=session, event_id=event.id)
        if consumption is None:
            return
        consumption.status = ConsumptionStatus.FAILED
        consumption.last_error = error[:1000]
        consumption.next_retry_at = get_datetime_cn() + timedelta(
            seconds=_retry_delay_seconds(consumption.attempt_count)
        )
        session.add(consumption)
        session.commit()
    logger.error(
        "通知事件消费失败，已安排重试 event_id=%s error=%s", event.id, error
    )


def _retry_delay_seconds(attempt_count: int) -> int:
    """指数退避：60s 起，最长 1 小时"""
    return min(
        CONSUMPTION_MAX_RETRY_SECONDS,
        CONSUMPTION_BASE_RETRY_SECONDS * (2 ** max(0, attempt_count - 1)),
    )


def _create_notifications(
    *,
    event: AutomationEvent,
    rules: list,
) -> None:
    """一次幂等生成：跳过已存在的接收人，站内即时送达、邮件进入异步投递"""
    with Session(engine) as session:
        email_deliveries: list[NotificationDelivery] = []
        in_app_notifications: list[Notification] = []
        created = 0
        for rule in rules:
            recipients = _resolve_recipients(
                session=session, recipients=rule.recipients
            )
            if not recipients:
                continue
            title = render_notification_template(rule.title_template, event.payload)
            content = render_notification_template(rule.content_template, event.payload)
            rule_key = rule.rule_id or rule.event_type
            for recipient in recipients:
                dedupe_key = build_dedupe_key(
                    event_id=event.id,
                    rule_key=rule_key,
                    recipient=str(recipient.user_id or recipient.email),
                )
                if (
                    get_notification_by_dedupe_key(
                        session=session, dedupe_key=dedupe_key
                    )
                    is not None
                ):
                    continue
                notification = create_notification(
                    session=session,
                    event_id=event.id,
                    event_type=event.event_type,
                    rule_id=rule_key,
                    user_id=recipient.user_id,
                    email_to=recipient.email,
                    title=title,
                    content=content,
                    template_name=rule.email_template,
                    payload=event.payload,
                    dedupe_key=dedupe_key,
                )
                session.flush()
                created += 1
                for channel in rule.channels:
                    if channel == ChannelType.IN_APP:
                        # 站内通知：通知落库即视为送达，不制造无意义的异步任务
                        create_delivery(
                            session=session,
                            notification_id=notification.id,
                            channel=channel,
                            status=DeliveryStatus.SENT,
                        )
                        in_app_notifications.append(notification)
                    else:
                        email_deliveries.append(
                            create_delivery(
                                session=session,
                                notification_id=notification.id,
                                channel=channel,
                            )
                        )
        session.commit()
        for notification in in_app_notifications:
            publish_notification_created(notification)
        for delivery in email_deliveries:
            enqueue_delivery(str(delivery.id))
        logger.info(
            "通知事件 %s 生成 %d 条通知（站内 %d / 邮件 %d）",
            event.event_type,
            created,
            len(in_app_notifications),
            len(email_deliveries),
        )


def _resolve_recipients(
    *,
    session: Session,
    recipients: RecipientsSpec,
) -> list[Recipient]:
    """解析规则接收人配置为具体接收人（当前支持角色与显式用户 ID）"""
    if recipients.user_ids:
        users = session.exec(
            select(User).where(col(User.id).in_(recipients.user_ids))
        ).all()
        return [
            Recipient(user_id=user.id, email=user.email)
            for user in users
            if user.id is not None
        ]
    if recipients.role == RecipientRole.SUPERUSER:
        users = session.exec(
            select(User).where(col(User.is_superuser).is_(True))
        ).all()
        return [
            Recipient(user_id=user.id, email=user.email)
            for user in users
            if user.id is not None
        ]
    return []
