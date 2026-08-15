"""通知中心：事件消费应用服务

监听全局 EventBus 事件 -> 匹配规则 -> 生成 Notification 与 Delivery
-> 落库 -> 派发 Celery 异步投递。同步段只做规则匹配与落库，不执行慢渠道调用。
"""

import logging
import uuid
from dataclasses import dataclass

from sqlmodel import Session, col, select

from app.core.db import engine
from app.modules.automation.models import AutomationEvent
from app.modules.notification.domain.constants import RecipientRole
from app.modules.notification.domain.rules import (
    RecipientsSpec,
    get_rules_for_event,
    render_notification_template,
)
from app.modules.notification.infrastructure.tasks import enqueue_delivery
from app.modules.notification.models import NotificationDelivery
from app.modules.notification.repositories.delivery import create_delivery
from app.modules.notification.repositories.notification import create_notification
from app.modules.user.models import User

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Recipient:
    """解析后的接收人"""

    user_id: uuid.UUID | None
    email: str | None


def process_notification_event(*, event: AutomationEvent) -> None:
    """按规则为事件生成通知并派发投递任务"""
    rules = get_rules_for_event(event.event_type)
    if not rules:
        return
    with Session(engine) as session:
        pending_deliveries: list[NotificationDelivery] = []
        for rule in rules:
            recipients = _resolve_recipients(
                session=session, recipients=rule.recipients
            )
            if not recipients:
                continue
            title = render_notification_template(rule.title_template, event.payload)
            content = render_notification_template(rule.content_template, event.payload)
            for recipient in recipients:
                notification = create_notification(
                    session=session,
                    event_id=event.id,
                    event_type=event.event_type,
                    rule_id=rule.rule_id or rule.event_type,
                    user_id=recipient.user_id,
                    email_to=recipient.email,
                    title=title,
                    content=content,
                    template_name=rule.email_template,
                    payload=event.payload,
                )
                session.flush()
                for channel in rule.channels:
                    delivery = create_delivery(
                        session=session,
                        notification_id=notification.id,
                        channel=channel,
                    )
                    pending_deliveries.append(delivery)
        session.commit()
        for delivery in pending_deliveries:
            enqueue_delivery(str(delivery.id))
        logger.info(
            "通知事件 %s 生成 %d 条投递记录",
            event.event_type,
            len(pending_deliveries),
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
        return [Recipient(user_id=user.id, email=user.email) for user in users]
    return []
