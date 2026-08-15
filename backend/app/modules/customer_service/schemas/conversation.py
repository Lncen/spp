"""客服模块：会话请求与响应模型"""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class ConversationPublic(SQLModel):
    """会话对外展示结构"""

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    status: str
    last_message_at: datetime | None = None
    last_message_preview: str | None = None
    created_at: datetime | None = None
    user_name: str | None = Field(default=None, title="用户展示名（管理端）")
    user_online: bool = Field(default=False, title="用户是否在线（管理端）")
    unread_count: int = Field(
        default=0,
        title="对方发来的未读消息数",
        description="当前查看者视角下对方发来且未读的消息数量",
    )


class ConversationsPublic(SQLModel):
    """会话列表"""

    data: list[ConversationPublic]
    count: int


class ConversationStatusUpdate(SQLModel):
    """会话状态更新请求"""

    status: str = Field(max_length=16, title="open / closed")


class ConversationCreate(SQLModel):
    """发起会话请求（管理端为指定用户发起时必填 user_id）"""

    user_id: uuid.UUID | None = Field(
        default=None,
        title="目标用户 ID",
        description="管理端主动联系的用户；普通用户忽略此字段",
    )
