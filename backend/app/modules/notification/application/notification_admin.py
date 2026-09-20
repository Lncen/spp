"""通知中心：管理端应用服务（记录查询 / 手动发送 / 投递重试）"""

import uuid
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.modules.automation.infrastructure.tasks.notification_delivery import (
    enqueue_delivery,
)
from app.modules.notification.application.realtime_publish import (
    publish_notification_created,
)
from app.modules.notification.domain.constants import (
    MANUAL_EMAIL_TEMPLATE,
    ChannelType,
    DeliveryStatus,
)
from app.modules.notification.models import Notification, NotificationDelivery
from app.modules.notification.repositories.delivery import (
    create_delivery,
    get_delivery_or_404,
    reset_delivery_for_retry,
)
from app.modules.notification.repositories.notification import (
    count_admin_deliveries,
    create_notification,
    delete_notification_with_deliveries,
    get_notifications_by_ids,
    list_admin_deliveries,
)
from app.modules.notification.schemas.notification import (
    DeliveryPublic,
    NotificationAdminItem,
    NotificationsAdminPublic,
)
from app.modules.user.models import User

VALID_CHANNELS = {ChannelType.IN_APP, ChannelType.EMAIL}


def _recipient_display_name(user: User) -> str:
    """生成接收对象展示名：全名 > 用户名 > 邮箱"""
    return user.full_name or user.username or user.email


def list_admin_notifications(
    *,
    session: Session,
    skip: int,
    limit: int,
    event_type: str | None,
    channel: str | None,
    status: str | None,
    keyword: str | None,
    recipient: str | None,
) -> NotificationsAdminPublic:
    """管理端分页查询通知记录（一行一条投递），返回接收人展示名"""
    deliveries = list_admin_deliveries(
        session=session,
        skip=skip,
        limit=limit,
        event_type=event_type,
        channel=channel,
        status=status,
        keyword=keyword,
        recipient=recipient,
    )
    count = count_admin_deliveries(
        session=session,
        event_type=event_type,
        channel=channel,
        status=status,
        keyword=keyword,
        recipient=recipient,
    )
    if not deliveries:
        return NotificationsAdminPublic(data=[], count=0)

    notifications = get_notifications_by_ids(
        session=session,
        notification_ids=[delivery.notification_id for delivery in deliveries],
    )
    user_ids = {
        notification.user_id
        for notification in notifications.values()
        if notification.user_id is not None
    }
    users: dict[uuid.UUID, User] = {}
    if user_ids:
        users = {
            user.id: user
            for user in session.exec(
                select(User).where(col(User.id).in_(user_ids))
            ).all()
            if user.id is not None
        }

    items: list[NotificationAdminItem] = []
    for delivery in deliveries:
        notification = notifications.get(delivery.notification_id)
        if notification is None:
            continue
        recipient: str | None = None
        if notification.user_id is not None and notification.user_id in users:
            recipient = _recipient_display_name(users[notification.user_id])
        elif notification.email_to:
            recipient = notification.email_to
        items.append(
            NotificationAdminItem(
                notification_id=notification.id,
                event_type=notification.event_type,
                title=notification.title,
                content=notification.content,
                payload_snapshot=notification.payload_snapshot,
                recipient=recipient,
                event_id=notification.event_id,
                rule_id=notification.rule_id,
                created_at=notification.created_at,
                read_at=notification.read_at,
                delivery=DeliveryPublic.model_validate(delivery),
            )
        )
    return NotificationsAdminPublic(data=items, count=count)


def send_manual_notification(
    *,
    session: Session,
    title: str,
    content: str,
    event_type: str,
    user_ids: list[uuid.UUID],
    channels: list[str],
    broadcast: bool = False,
) -> tuple[int, int, int]:
    """手动发送通知：为每个接收人生成通知与投递记录。

    broadcast=True 时接收人为全部启用用户（忽略 user_ids）；
    返回 (投递条数, 站内已送达条数, 邮件成功入队条数)；
    站内通知落库即送达，不经过异步投递；邮件入队失败不抛异常，
    未入队的记录保持 pending 由兜底扫描任务补投。
    """
    invalid_channels = set(channels) - VALID_CHANNELS
    if invalid_channels:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的投递渠道: {', '.join(sorted(invalid_channels))}",
        )
    if broadcast:
        users = session.exec(
            select(User).where(col(User.is_active).is_(True))
        ).all()
        if not users:
            raise HTTPException(status_code=400, detail="当前没有可接收的启用用户")
    else:
        users = session.exec(
            select(User).where(col(User.id).in_(user_ids))
        ).all()
        if not users:
            raise HTTPException(status_code=400, detail="未找到有效的接收用户")
        missing_ids = set(user_ids) - {
            user.id for user in users if user.id is not None
        }
        if missing_ids:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"以下用户不存在: "
                    f"{', '.join(str(uid) for uid in sorted(missing_ids))}"
                ),
            )

    payload: dict[str, Any] = {"title": title, "content": content}
    email_deliveries: list[NotificationDelivery] = []
    in_app_notifications: list[Notification] = []
    delivery_count = 0
    for user in users:
        if user.id is None:
            continue
        notification = create_notification(
            session=session,
            event_id=None,
            event_type=event_type,
            rule_id=None,
            user_id=user.id,
            email_to=user.email,
            title=title,
            content=content,
            template_name=MANUAL_EMAIL_TEMPLATE,
            payload=payload,
        )
        session.flush()
        for channel in channels:
            delivery_count += 1
            if channel == ChannelType.IN_APP:
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
    enqueued = 0
    for delivery in email_deliveries:
        if enqueue_delivery(str(delivery.id)):
            enqueued += 1
    return delivery_count, len(in_app_notifications), enqueued


def retry_delivery(
    *,
    session: Session,
    delivery_id: uuid.UUID,
) -> NotificationDelivery:
    """重试失败的投递：重置状态并重新入队，返回重置后的投递记录"""
    delivery = get_delivery_or_404(session=session, delivery_id=delivery_id)
    if delivery.status != DeliveryStatus.FAILED:
        raise HTTPException(status_code=400, detail="仅失败状态的投递可重试")
    reset_delivery_for_retry(session=session, delivery=delivery)
    session.commit()
    enqueue_delivery(str(delivery.id))
    return delivery


def delete_notification_record(
    *,
    session: Session,
    notification_id: uuid.UUID,
) -> None:
    """删除通知记录及其全部投递记录"""
    delete_notification_with_deliveries(
        session=session,
        notification_id=notification_id,
    )
    session.commit()
