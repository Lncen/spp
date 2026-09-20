"""聊天模块：聊天成员模型（成员关系 + 已读游标）"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin
from app.core.time import get_datetime_cn
from app.modules.chat.domain.constants import ParticipantRole


class ChatParticipant(BaseModelMixin, SQLModel, table=True):
    """聊天成员：同时承担成员关系与已读游标

    不额外建 `ChatMember` / `ReadStatus` 表：一个成员在一条聊天里只有一行，
    `last_read_message_id` 记录该成员读到哪里，未读数由它推算。
    """

    __tablename__ = "chat_participants"
    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "user_id",
            name="uq_chat_participants_chat_user",
        ),
    )

    chat_id: uuid.UUID = Field(
        foreign_key="chats.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
        title="聊天 ID",
    )
    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
        title="用户 ID",
    )
    role: str = Field(
        default=ParticipantRole.MEMBER,
        max_length=16,
        nullable=False,
        title="成员角色",
        description="DIRECT 用 MEMBER；GROUP 用 OWNER / MEMBER",
    )
    joined_at: datetime = Field(
        default_factory=get_datetime_cn,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
        nullable=False,
        title="加入时间",
    )
    last_read_message_id: uuid.UUID | None = Field(
        default=None,
        title="已读游标",
        description="该成员最后已读的消息 ID，只允许沿消息顺序向前推进",
    )
