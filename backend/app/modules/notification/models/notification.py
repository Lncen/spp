"""通知中心：通知实例模型

一条 Notification 表达「给谁、发了什么」（业务语义）；
投递过程与结果由 NotificationDelivery 记录（工程语义）。
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin


class Notification(BaseModelMixin, SQLModel, table=True):
    """通知实例：由事件按规则生成，供用户查询与已读管理"""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_notifications_dedupe_key"),
    )

    event_id: uuid.UUID | None = Field(
        default=None,
        index=True,
        title="来源事件 ID",
        description="触发本通知的自动化事件 ID，不建外键以解耦事件清理策略",
    )
    event_type: str = Field(
        max_length=64,
        index=True,
        nullable=False,
        title="事件类型",
        description="触发通知的业务事件类型，如 order.fulfillment_failed",
    )
    rule_id: str | None = Field(
        default=None,
        max_length=64,
        index=True,
        title="规则标识",
        description="命中的通知规则标识（代码注册表键）",
    )
    dedupe_key: str | None = Field(
        default=None,
        max_length=255,
        title="幂等键",
        description=(
            "事件触发的通知按「事件 ID:规则:接收人」唯一，事件重放 / 重试不会重复生成；"
            "手动发送的通知留空，允许重复发送"
        ),
    )
    user_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        ondelete="SET NULL",
        index=True,
        title="接收用户 ID",
        description="站内通知的接收用户；用户删除后置空",
    )
    email_to: str | None = Field(
        default=None,
        max_length=255,
        title="接收邮箱",
        description="邮件渠道的接收地址，无对应用户时也可独立存在",
    )
    title: str = Field(
        max_length=255,
        nullable=False,
        title="通知标题",
    )
    content: str = Field(
        default="",
        max_length=2000,
        title="通知内容",
        description="渲染后的站内通知内容（纯文本）",
    )
    template_name: str | None = Field(
        default=None,
        max_length=128,
        title="邮件模板名",
        description="邮件渠道使用的 build 目录下的模板文件名，如 notification_order_failed.html",
    )
    payload_snapshot: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        title="事件载荷快照",
        description="触发通知时的事件载荷，用于审计与模板渲染",
    )
    read_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
        index=True,
        title="已读时间",
        description="站内通知被用户标记已读的时间，未读为 None",
    )
