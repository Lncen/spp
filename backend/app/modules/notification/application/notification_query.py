"""通知中心：通知查询与已读应用服务"""

import uuid
from datetime import UTC, datetime

from sqlmodel import Session

from app.modules.notification.models import Notification
from app.modules.notification.repositories.notification import (
    count_unread_notifications,
    count_user_notifications,
    get_user_notification_or_404,
    list_user_notifications,
    mark_all_read,
    mark_notification_read,
)
from app.modules.notification.schemas.notification import (
    NotificationsPublic,
    UnreadCount,
)


def get_my_notifications(
    *,
    session: Session,
    user_id: uuid.UUID,
    skip: int,
    limit: int,
    unread_only: bool,
) -> NotificationsPublic:
    """查询当前用户通知分页列表（含未读数）"""
    data = list_user_notifications(
        session=session,
        user_id=user_id,
        skip=skip,
        limit=limit,
        unread_only=unread_only,
    )
    count = count_unread_notifications(session=session, user_id=user_id)
    total = count_user_notifications(
        session=session, user_id=user_id, unread_only=unread_only
    )
    return NotificationsPublic(data=data, count=total, unread_count=count)


def get_unread_count(*, session: Session, user_id: uuid.UUID) -> UnreadCount:
    """查询当前用户未读通知数"""
    return UnreadCount(
        unread_count=count_unread_notifications(session=session, user_id=user_id)
    )


def mark_my_notification_read(
    *,
    session: Session,
    user_id: uuid.UUID,
    notification_id: uuid.UUID,
) -> Notification:
    """标记当前用户单条通知已读"""
    notification = get_user_notification_or_404(
        session=session,
        notification_id=notification_id,
        user_id=user_id,
    )
    mark_notification_read(
        session=session,
        notification=notification,
        now=datetime.now(UTC),
    )
    session.commit()
    session.refresh(notification)
    return notification


def mark_my_all_read(*, session: Session, user_id: uuid.UUID) -> int:
    """批量标记当前用户全部未读通知为已读，返回更新条数"""
    updated = mark_all_read(
        session=session,
        user_id=user_id,
        now=datetime.now(UTC),
    )
    session.commit()
    return updated
