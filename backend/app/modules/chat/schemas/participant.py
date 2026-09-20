"""聊天模块：聊天成员请求与响应模型"""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class ParticipantAdd(SQLModel):
    """把用户加入群聊（成员管理）"""

    user_id: uuid.UUID
    role: str | None = Field(
        default=None,
        title="成员角色",
        description="留空时按聊天类型使用默认角色",
    )


class ParticipantPublic(SQLModel):
    """聊天成员展示结构"""

    id: uuid.UUID
    user_id: uuid.UUID
    role: str
    display_name: str | None = None
    display_avatar_url: str | None = None
    is_online: bool = Field(
        default=False,
        title="是否在线",
        description="来自 realtime 的 Presence（Redis），Redis 不可用时按离线展示",
    )
    joined_at: datetime | None = None
    last_read_message_id: uuid.UUID | None = None


class ParticipantsPublic(SQLModel):
    """聊天成员列表"""

    data: list[ParticipantPublic]
    count: int
