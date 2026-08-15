"""通知中心：API 数据传输对象"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, model_validator
from sqlmodel import SQLModel


class NotificationPublic(SQLModel):
    """通知对外展示结构"""

    id: uuid.UUID
    title: str
    content: str
    event_type: str
    payload_snapshot: dict[str, Any]
    created_at: datetime | None
    read_at: datetime | None


class NotificationsPublic(SQLModel):
    """通知分页列表"""

    data: list[NotificationPublic]
    count: int
    unread_count: int


class UnreadCount(SQLModel):
    """未读通知数"""

    unread_count: int


class DeliveryPublic(SQLModel):
    """管理端：投递记录展示结构"""

    id: uuid.UUID
    channel: str
    status: str
    attempt_count: int
    max_attempts: int
    error_message: str | None = None
    sent_at: datetime | None = None


class NotificationAdminItem(SQLModel):
    """管理端：通知记录列表项（按投递粒度一行）"""

    notification_id: uuid.UUID
    event_type: str
    title: str
    content: str
    payload_snapshot: dict[str, Any] = Field(default_factory=dict)
    recipient: str | None = Field(default=None, title="接收对象展示名")
    event_id: uuid.UUID | None = None
    rule_id: str | None = None
    created_at: datetime | None = None
    read_at: datetime | None = None
    delivery: DeliveryPublic


class NotificationsAdminPublic(SQLModel):
    """管理端：通知记录分页列表"""

    data: list[NotificationAdminItem]
    count: int


class NotificationSendRequest(SQLModel):
    """管理端：手动发送通知请求"""

    title: str = Field(min_length=1, max_length=255)
    content: str = Field(default="", max_length=2000)
    event_type: str = Field(default="manual", min_length=1, max_length=64)
    user_ids: list[uuid.UUID] = Field(
        default_factory=list,
        title="接收用户 ID 列表",
        description="broadcast=false 时必填，至少一个",
    )
    channels: list[str] = Field(min_length=1, title="投递渠道列表")
    broadcast: bool = Field(
        default=False,
        title="群发",
        description="为 true 时发送给全部启用用户，忽略 user_ids",
    )

    @model_validator(mode="after")
    def _check_recipients(self) -> NotificationSendRequest:
        """非群发时必须指定至少一个接收用户"""
        if not self.broadcast and not self.user_ids:
            raise ValueError("user_ids 至少需要一个接收用户")
        return self
