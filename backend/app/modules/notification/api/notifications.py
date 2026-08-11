"""通知中心：用户通知查询与已读 API"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.common.models import Message
from app.modules.notification.application.notification_query import (
    get_my_notifications,
    get_unread_count,
    mark_my_all_read,
    mark_my_notification_read,
)
from app.modules.notification.schemas.notification import (
    NotificationPublic,
    NotificationsPublic,
    UnreadCount,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=NotificationsPublic)
def read_my_notifications(
    session: SessionDep,
    current_user: CurrentUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    unread_only: bool = False,
) -> NotificationsPublic:
    """查询当前用户的通知列表（最新在前），unread_only=true 时只返回未读"""
    return get_my_notifications(
        session=session,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        unread_only=unread_only,
    )


@router.get("/unread-count", response_model=UnreadCount)
def read_unread_count(
    session: SessionDep,
    current_user: CurrentUser,
) -> UnreadCount:
    """查询当前用户未读通知数"""
    return get_unread_count(session=session, user_id=current_user.id)


@router.post("/{notification_id}/read", response_model=NotificationPublic)
def mark_read(
    session: SessionDep,
    current_user: CurrentUser,
    notification_id: uuid.UUID,
) -> NotificationPublic:
    """标记单条通知为已读"""
    notification = mark_my_notification_read(
        session=session,
        user_id=current_user.id,
        notification_id=notification_id,
    )
    return NotificationPublic.model_validate(notification)


@router.post("/read-all", response_model=Message, status_code=status.HTTP_200_OK)
def mark_all_read(
    session: SessionDep,
    current_user: CurrentUser,
) -> Message:
    """将当前用户全部未读通知标记为已读"""
    updated = mark_my_all_read(session=session, user_id=current_user.id)
    return Message(message=f"已标记 {updated} 条通知为已读")
