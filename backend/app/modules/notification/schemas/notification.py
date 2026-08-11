"""通知中心：API 数据传输对象"""

import uuid
from datetime import datetime
from typing import Any

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
