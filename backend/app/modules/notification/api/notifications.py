"""通知中心：用户通知查询与已读 API"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    CurrentUser,
    SessionDep,
    require_permission,
)
from app.common.models import Message
from app.modules.notification.application.notification_admin import (
    delete_notification_record,
    list_admin_notifications,
    retry_delivery,
    send_manual_notification,
)
from app.modules.notification.application.notification_query import (
    delete_my_notification,
    get_my_notifications,
    get_unread_count,
    get_unread_summary,
    mark_my_all_read,
    mark_my_notification_read,
)
from app.modules.notification.schemas.notification import (
    DeliveryPublic,
    NotificationPublic,
    NotificationsAdminPublic,
    NotificationSendRequest,
    NotificationsPublic,
    UnreadCount,
    UnreadSummary,
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


@router.get("/unread-summary", response_model=UnreadSummary)
def read_unread_summary(
    session: SessionDep,
    current_user: CurrentUser,
) -> UnreadSummary:
    """查询侧边栏总未读数：系统通知未读 + 客服会话未读"""
    return get_unread_summary(session=session, user=current_user)


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


@router.delete("/{notification_id}", response_model=Message)
def delete_my_notification_endpoint(
    session: SessionDep,
    current_user: CurrentUser,
    notification_id: uuid.UUID,
) -> Message:
    """删除当前用户的通知记录（级联删除其全部投递记录）"""
    delete_my_notification(
        session=session,
        user_id=current_user.id,
        notification_id=notification_id,
    )
    return Message(message="通知已删除")


@router.get(
    "/admin",
    dependencies=[Depends(require_permission("notification:view"))],
    response_model=NotificationsAdminPublic,
)
def read_admin_notifications(
    session: SessionDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    event_type: str | None = Query(default=None, max_length=64),
    channel: str | None = Query(default=None, max_length=32),
    status: str | None = Query(default=None, max_length=16),
    keyword: str | None = Query(default=None, max_length=64),
    recipient: str | None = Query(default=None, max_length=255),
) -> NotificationsAdminPublic:
    """管理端分页查询全部通知记录（一行一条投递），可按事件类型/渠道/状态/关键字/接收人筛选"""
    return list_admin_notifications(
        session=session,
        skip=skip,
        limit=limit,
        event_type=event_type,
        channel=channel,
        status=status,
        keyword=keyword,
        recipient=recipient,
    )


@router.post(
    "/admin",
    dependencies=[Depends(require_permission("notification:create"))],
    response_model=Message,
)
def send_admin_notification(
    session: SessionDep,
    body: NotificationSendRequest,
) -> Message:
    """管理端手动发送通知（站内/邮件），投递异步执行；broadcast=true 时群发给全部启用用户"""
    created, enqueued = send_manual_notification(
        session=session,
        title=body.title,
        content=body.content,
        event_type=body.event_type,
        user_ids=body.user_ids,
        channels=body.channels,
        broadcast=body.broadcast,
    )
    message = f"已创建 {created} 条投递记录，正在异步发送"
    failed = created - enqueued
    if failed:
        message = (
            f"已创建 {created} 条投递记录，其中 {failed} 条入队失败，"
            "将由兜底任务自动补投"
        )
    return Message(message=message)


@router.post(
    "/admin/deliveries/{delivery_id}/retry",
    dependencies=[Depends(require_permission("notification:retry"))],
    response_model=DeliveryPublic,
)
def retry_admin_delivery(
    session: SessionDep,
    delivery_id: uuid.UUID,
) -> DeliveryPublic:
    """重试失败的投递记录，重新入队发送"""
    delivery = retry_delivery(session=session, delivery_id=delivery_id)
    return DeliveryPublic.model_validate(delivery)


@router.delete(
    "/admin/{notification_id}",
    dependencies=[Depends(require_permission("notification:delete"))],
    response_model=Message,
)
def delete_admin_notification(
    session: SessionDep,
    notification_id: uuid.UUID,
) -> Message:
    """管理端删除通知记录（级联删除其全部投递记录）"""
    delete_notification_record(
        session=session,
        notification_id=notification_id,
    )
    return Message(message="通知已删除")
