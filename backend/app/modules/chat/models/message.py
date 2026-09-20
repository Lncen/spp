"""聊天模块：消息模型"""

import uuid

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin
from app.modules.chat.domain.constants import (
    MAX_MESSAGE_CONTENT_LENGTH,
    MessageType,
)


class Message(BaseModelMixin, SQLModel, table=True):
    """聊天消息：文本或文件消息

    主键是 UUID v4，**没有时间顺序**，因此消息新旧一律按 `(created_at, id)` 判断，
    分页也使用该组合做游标。
    """

    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint(
            "sender_id",
            "client_message_id",
            name="uq_chat_messages_sender_client_message",
        ),
        Index(
            "ix_chat_messages_chat_created_id",
            "chat_id",
            "created_at",
            "id",
        ),
    )

    chat_id: uuid.UUID = Field(
        foreign_key="chats.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
        title="聊天 ID",
    )
    sender_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        ondelete="SET NULL",
        index=True,
        title="发送用户 ID",
        description="消息发送者；用户被删除后置空，消息本身保留",
    )
    message_type: str = Field(
        default=MessageType.TEXT,
        max_length=16,
        nullable=False,
        title="消息类型",
        description="TEXT=文本 / FILE=文件",
    )
    content: str = Field(
        default="",
        max_length=MAX_MESSAGE_CONTENT_LENGTH,
        title="消息内容",
        description="文本消息正文；文件消息可放说明文字",
    )
    file_name: str | None = Field(
        default=None,
        max_length=255,
        title="文件名",
        description="仅文件消息使用，展示用原始文件名",
    )
    file_path: str | None = Field(
        default=None,
        max_length=512,
        title="文件路径",
        description="仅文件消息使用，复用现有上传能力的存储路径，不新建文件存储系统",
    )
    client_message_id: str | None = Field(
        default=None,
        max_length=64,
        title="客户端消息 ID",
        description="客户端生成的幂等键：重试发送同一 ID 只会落一条消息",
    )
