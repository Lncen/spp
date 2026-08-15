"""客服模块：会话消息模型"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin
from app.modules.customer_service.domain.constants import SenderRole


class ConversationMessage(BaseModelMixin, SQLModel, table=True):
    """客服消息：归属会话，记录发送方与已读状态"""

    __tablename__ = "customer_service_messages"

    conversation_id: uuid.UUID = Field(
        foreign_key="customer_service_conversations.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
        title="会话 ID",
    )
    sender_id: uuid.UUID = Field(
        foreign_key="user.id",
        ondelete="SET NULL",
        index=True,
        nullable=True,
        title="发送用户 ID",
    )
    sender_role: str = Field(
        default=SenderRole.USER,
        max_length=16,
        nullable=False,
        title="发送方角色",
        description="user=用户 / admin=管理员",
    )
    content: str = Field(
        max_length=2000,
        nullable=False,
        title="消息内容",
    )
    read_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
        title="已读时间",
        description="对方阅读该消息的时间，未读为 None",
    )
