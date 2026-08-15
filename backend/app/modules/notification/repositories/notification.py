"""通知中心：通知实例数据访问"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, delete, func, or_, select, update

from app.modules.notification.models import Notification, NotificationDelivery
from app.modules.user.models import User


def _keyword_filter(keyword: str | None):
    """构造标题/内容模糊匹配条件，无关键字时返回 None"""
    if not keyword:
        return None
    pattern = f"%{keyword.strip()}%"
    return or_(
        Notification.title.ilike(pattern),
        Notification.content.ilike(pattern),
    )


def _recipient_filter(recipient: str | None):
    """构造接收人模糊匹配条件（用户全名/用户名/邮箱或直接邮箱），无关键词时返回 None"""
    if not recipient:
        return None
    pattern = f"%{recipient.strip()}%"
    return or_(
        User.full_name.ilike(pattern),
        User.username.ilike(pattern),
        User.email.ilike(pattern),
        Notification.email_to.ilike(pattern),
    )


def create_notification(
    *,
    session: Session,
    event_id: uuid.UUID | None,
    event_type: str,
    rule_id: str,
    user_id: uuid.UUID | None,
    email_to: str | None,
    title: str,
    content: str,
    template_name: str | None,
    payload: dict[str, Any],
) -> Notification:
    """创建通知实例并加入会话（不提交，由调用方控制事务）"""
    notification = Notification(
        event_id=event_id,
        event_type=event_type,
        rule_id=rule_id,
        user_id=user_id,
        email_to=email_to,
        title=title,
        content=content,
        template_name=template_name,
        payload_snapshot=payload,
    )
    session.add(notification)
    return notification


def list_user_notifications(
    *,
    session: Session,
    user_id: uuid.UUID,
    skip: int,
    limit: int,
    unread_only: bool,
) -> list[Notification]:
    """分页查询用户通知，最新在前"""
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(col(Notification.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    if unread_only:
        stmt = stmt.where(col(Notification.read_at).is_(None))
    return list(session.exec(stmt).all())


def count_user_notifications(
    *,
    session: Session,
    user_id: uuid.UUID,
    unread_only: bool,
) -> int:
    """统计用户通知总数"""
    stmt = select(func.count()).select_from(Notification).where(
        Notification.user_id == user_id
    )
    if unread_only:
        stmt = stmt.where(col(Notification.read_at).is_(None))
    return session.exec(stmt).one()


def count_unread_notifications(
    *,
    session: Session,
    user_id: uuid.UUID,
) -> int:
    """统计用户未读通知数"""
    return count_user_notifications(session=session, user_id=user_id, unread_only=True)


def list_admin_deliveries(
    *,
    session: Session,
    skip: int,
    limit: int,
    event_type: str | None,
    channel: str | None,
    status: str | None,
    keyword: str | None,
    recipient: str | None,
) -> list[NotificationDelivery]:
    """管理端分页查询全部投递记录（含所属通知），最新在前"""
    stmt = (
        select(NotificationDelivery)
        .join(Notification, NotificationDelivery.notification_id == Notification.id)
        .order_by(
            col(Notification.created_at).desc(),
            col(NotificationDelivery.created_at).desc(),
        )
        .offset(skip)
        .limit(limit)
    )
    if event_type:
        stmt = stmt.where(Notification.event_type == event_type)
    if channel:
        stmt = stmt.where(NotificationDelivery.channel == channel)
    if status:
        stmt = stmt.where(NotificationDelivery.status == status)
    keyword_filter = _keyword_filter(keyword)
    if keyword_filter is not None:
        stmt = stmt.where(keyword_filter)
    recipient_filter = _recipient_filter(recipient)
    if recipient_filter is not None:
        stmt = stmt.outerjoin(User, Notification.user_id == User.id).where(
            recipient_filter
        )
    return list(session.exec(stmt).all())


def count_admin_deliveries(
    *,
    session: Session,
    event_type: str | None,
    channel: str | None,
    status: str | None,
    keyword: str | None,
    recipient: str | None,
) -> int:
    """统计管理端投递记录总数（与列表同条件）"""
    stmt = (
        select(func.count())
        .select_from(NotificationDelivery)
        .join(Notification, NotificationDelivery.notification_id == Notification.id)
    )
    if event_type:
        stmt = stmt.where(Notification.event_type == event_type)
    if channel:
        stmt = stmt.where(NotificationDelivery.channel == channel)
    if status:
        stmt = stmt.where(NotificationDelivery.status == status)
    keyword_filter = _keyword_filter(keyword)
    if keyword_filter is not None:
        stmt = stmt.where(keyword_filter)
    recipient_filter = _recipient_filter(recipient)
    if recipient_filter is not None:
        stmt = stmt.outerjoin(User, Notification.user_id == User.id).where(
            recipient_filter
        )
    return session.exec(stmt).one()


def get_notifications_by_ids(
    *,
    session: Session,
    notification_ids: list[uuid.UUID],
) -> dict[uuid.UUID, Notification]:
    """批量查询通知，返回 id -> Notification 映射"""
    if not notification_ids:
        return {}
    notifications = session.exec(
        select(Notification).where(Notification.id.in_(notification_ids))
    ).all()
    return {notification.id: notification for notification in notifications}


def get_user_notification_or_404(
    *,
    session: Session,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Notification:
    """按 ID 获取当前用户的通知，不存在或非本人时抛 404"""
    notification = session.get(Notification, notification_id)
    if not notification or notification.user_id != user_id:
        raise HTTPException(status_code=404, detail="通知不存在")
    return notification


def mark_notification_read(
    *,
    session: Session,
    notification: Notification,
    now: datetime,
) -> Notification:
    """标记单条通知已读（幂等）"""
    if notification.read_at is None:
        notification.read_at = now
        session.add(notification)
    return notification


def mark_all_read(
    *,
    session: Session,
    user_id: uuid.UUID,
    now: datetime,
) -> int:
    """批量标记当前用户全部未读通知为已读，返回更新条数"""
    result = session.exec(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            col(Notification.read_at).is_(None),
        )
        .values(read_at=now)
    )
    return result.rowcount or 0


def delete_user_notification(
    *,
    session: Session,
    user_id: uuid.UUID,
    notification_id: uuid.UUID,
) -> None:
    """删除当前用户的通知及其全部投递记录（非本人抛 404）"""
    notification = get_user_notification_or_404(
        session=session,
        notification_id=notification_id,
        user_id=user_id,
    )
    delete_notification_with_deliveries(
        session=session,
        notification_id=notification.id,
    )


def delete_notification_with_deliveries(
    *,
    session: Session,
    notification_id: uuid.UUID,
) -> Notification:
    """删除通知实例及其全部投递记录（显式删除，不依赖数据库级联配置）"""
    notification = session.get(Notification, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="通知不存在")
    deliveries = session.exec(
        select(NotificationDelivery).where(
            NotificationDelivery.notification_id == notification_id
        )
    ).all()
    for delivery in deliveries:
        session.delete(delivery)
    session.delete(notification)
    return notification


def purge_old_notifications(
    *,
    session: Session,
    before: datetime,
    limit: int,
) -> int:
    """物理删除创建时间早于 before 的通知及其全部投递记录，返回删除通知条数。

    显式先删投递记录再删通知（不依赖数据库级联配置），分批由调用方控制。
    """
    ids = session.exec(
        select(Notification.id)
        .where(col(Notification.created_at) < before)
        .limit(limit)
    ).all()
    if not ids:
        return 0
    session.exec(
        delete(NotificationDelivery).where(
            NotificationDelivery.notification_id.in_(ids)
        )
    )
    session.exec(delete(Notification).where(Notification.id.in_(ids)))
    session.commit()
    return len(ids)
