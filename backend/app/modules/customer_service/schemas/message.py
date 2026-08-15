"""客服模块：消息请求与响应模型"""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.modules.customer_service.schemas.conversation import ConversationPublic


class MessageCreate(SQLModel):
    """发送消息请求"""

    content: str = Field(min_length=1, max_length=2000, title="消息内容")


class MessagePublic(SQLModel):
    """消息对外展示结构"""

    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID | None = None
    sender_role: str
    content: str
    read_at: datetime | None = None
    created_at: datetime | None = None


class MessagesPublic(SQLModel):
    """会话消息列表"""

    data: list[MessagePublic]
    count: int
    conversation: ConversationPublic


class OnlineStatusPublic(SQLModel):
    """在线状态批量查询结果"""

    online: dict[str, bool]
