"""聊天模块：消息请求与响应模型"""

import uuid
from datetime import datetime

from pydantic import model_validator
from sqlmodel import Field, SQLModel

from app.modules.chat.domain.constants import (
    MAX_MESSAGE_CONTENT_LENGTH,
    MessageType,
)


class MessageCreate(SQLModel):
    """发送消息入参（HTTP 与 Socket.IO 共用）"""

    content: str = Field(
        default="",
        max_length=MAX_MESSAGE_CONTENT_LENGTH,
        title="消息内容",
    )
    message_type: str = Field(
        default=MessageType.TEXT,
        max_length=16,
        title="消息类型",
    )
    file_name: str | None = Field(default=None, max_length=255, title="文件名")
    file_path: str | None = Field(
        default=None,
        max_length=512,
        title="文件路径",
        description="先走现有上传能力取得文件元数据，再发送文件消息，不通过实时通道传二进制",
    )
    client_message_id: str | None = Field(
        default=None,
        max_length=64,
        title="客户端消息 ID",
        description="客户端生成的幂等键，重复发送同一 ID 只落一条消息",
    )

    @model_validator(mode="after")
    def _check_content(self) -> MessageCreate:
        """文本消息必须有内容，文件消息必须有文件路径"""
        if self.message_type == MessageType.FILE:
            if not self.file_path:
                raise ValueError("文件消息必须提供 file_path")
            return self
        if self.message_type != MessageType.TEXT:
            raise ValueError("不支持的消息类型")
        if not self.content.strip():
            raise ValueError("文本消息内容不能为空")
        return self


class MessagePublic(SQLModel):
    """消息展示结构"""

    id: uuid.UUID
    chat_id: uuid.UUID
    sender_id: uuid.UUID | None = Field(
        default=None,
        description="发送者；用户被删除后为 None",
    )
    sender_name: str | None = None
    message_type: str
    content: str
    file_name: str | None = None
    file_path: str | None = None
    client_message_id: str | None = None
    created_at: datetime | None = None


class MessagesPublic(SQLModel):
    """消息分页结果"""

    data: list[MessagePublic]
    count: int = Field(
        title="聊天内消息总数",
        description="前端据此判断是否还有更早的历史消息",
    )
