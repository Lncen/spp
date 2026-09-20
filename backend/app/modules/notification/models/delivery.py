"""通知中心：渠道投递记录模型"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin
from app.modules.notification.domain.constants import DeliveryStatus


class NotificationDelivery(BaseModelMixin, SQLModel, table=True):
    """渠道投递记录：追踪每个渠道的发送过程、重试与结果"""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "notification_id",
            "channel",
            name="uq_notification_deliveries_notification_channel",
        ),
    )

    notification_id: uuid.UUID = Field(
        foreign_key="notifications.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
        title="通知 ID",
        description="所属通知，通知删除时级联删除投递记录",
    )
    channel: str = Field(
        max_length=32,
        index=True,
        nullable=False,
        title="渠道",
        description="如 in_app / email",
    )
    status: str = Field(
        default=DeliveryStatus.PENDING,
        max_length=16,
        index=True,
        nullable=False,
        title="投递状态",
        description="pending -> sending -> sent / failed / canceled",
    )
    attempt_count: int = Field(
        default=0,
        nullable=False,
        title="已尝试次数",
        description="包含当前这次尝试",
    )
    max_attempts: int = Field(
        default=3,
        nullable=False,
        title="最大尝试次数",
        description="超过后投递进入 failed 终态",
    )
    error_message: str | None = Field(
        default=None,
        max_length=1000,
        title="错误信息",
        description="最近一次投递失败的原因",
    )
    sent_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
        title="发送成功时间",
    )
