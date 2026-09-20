"""聊天模块：聊天模型"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin
from app.modules.chat.domain.constants import (
    MAX_MESSAGE_PREVIEW_LENGTH,
    ChatStatus,
)


class Chat(BaseModelMixin, SQLModel, table=True):
    """聊天：私聊 / 群聊的唯一承载

    三类聊天共用一张表，通过 `type` 区分，并用唯一约束保证业务上的「只有一条」：

    - `DIRECT`：`direct_key` 唯一，同一对用户无论谁先发起都只有一条私聊；
    - `GROUP`：使用 `name` 作为群名称，成员关系由 `ChatParticipant` 维护。
    """

    __tablename__ = "chats"
    __table_args__ = (
        UniqueConstraint("direct_key", name="uq_chats_direct_key"),
    )

    type: str = Field(
        max_length=16,
        index=True,
        nullable=False,
        title="聊天类型",
        description="DIRECT=私聊 / GROUP=群聊",
    )
    status: str = Field(
        default=ChatStatus.ACTIVE,
        max_length=16,
        index=True,
        nullable=False,
        title="聊天状态",
        description="ACTIVE=进行中 / CLOSED=已关闭",
    )
    direct_key: str | None = Field(
        default=None,
        max_length=80,
        title="私聊唯一键",
        description="较小用户 ID + ':' + 较大用户 ID，仅 DIRECT 类型写入",
    )
    name: str | None = Field(
        default=None,
        max_length=100,
        title="聊天名称",
        description="群聊名称；私聊留空，由前端按参与者展示",
    )
    last_message_id: uuid.UUID | None = Field(
        default=None,
        title="最后消息 ID",
        description="列表展示用冗余字段，不建外键，避免与消息表形成循环依赖",
    )
    last_message_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
        index=True,
        title="最后消息时间",
    )
    last_message_preview: str | None = Field(
        default=None,
        max_length=MAX_MESSAGE_PREVIEW_LENGTH,
        title="最后消息预览",
    )
