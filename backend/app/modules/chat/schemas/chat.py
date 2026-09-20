"""聊天模块：聊天请求与响应模型"""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class ChatDirectCreate(SQLModel):
    """创建（或复用）与指定用户的私聊"""

    user_id: uuid.UUID = Field(title="对方用户 ID")


class ChatGroupCreate(SQLModel):
    """创建群聊"""

    name: str = Field(min_length=1, max_length=100, title="群名称")
    member_ids: list[uuid.UUID] = Field(
        default_factory=list,
        title="初始成员",
        description="除创建者（群主）外的初始成员，去重后加入",
    )


class ChatPublic(SQLModel):
    """聊天展示结构"""

    id: uuid.UUID
    type: str
    status: str
    name: str | None = None
    display_name: str | None = Field(
        default=None,
        title="展示名称",
        description="按聊天类型解析：私聊为对方昵称，群聊为群名",
    )
    display_avatar_url: str | None = Field(default=None, title="展示头像 URL")
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    unread_count: int = Field(default=0, title="未读消息数")
    created_at: datetime | None = None


class ChatsPublic(SQLModel):
    """聊天列表"""

    data: list[ChatPublic]
    count: int


class ChatReadResult(SQLModel):
    """标记已读结果"""

    chat_id: uuid.UUID
    last_read_message_id: uuid.UUID | None = None
    unread_count: int = Field(default=0, title="该聊天剩余未读数")


class ChatUnreadCount(SQLModel):
    """消息未读总数（侧边栏聊天角标）"""

    unread_count: int


class ChatReadBody(SQLModel):
    """标记已读请求体"""

    message_id: uuid.UUID = Field(title="已读到的消息 ID")
