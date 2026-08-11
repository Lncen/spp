"""通知中心：通知实例数据访问"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.modules.notification.models import Notification


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
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id, col(Notification.read_at).is_(None))
    )
    notifications = session.exec(stmt).all()
    for notification in notifications:
        notification.read_at = now
        session.add(notification)
    return len(notifications)
