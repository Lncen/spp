"""客服模块：会话模型"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin
from app.modules.customer_service.domain.constants import ConversationStatus


class Conversation(BaseModelMixin, SQLModel, table=True):
    """客服会话：一个用户一条活跃会话，管理端统一接待"""

    __tablename__ = "customer_service_conversations"

    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
        title="用户 ID",
        description="发起会话的用户",
    )
    status: str = Field(
        default=ConversationStatus.OPEN,
        max_length=16,
        index=True,
        nullable=False,
        title="会话状态",
        description="open=进行中 / closed=已关闭",
    )
    last_message_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
        index=True,
        title="最后消息时间",
    )
    last_message_preview: str | None = Field(
        default=None,
        max_length=200,
        title="最后消息预览",
    )
