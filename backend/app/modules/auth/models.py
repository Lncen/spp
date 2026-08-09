"""认证模块：数据库模型"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.core.mixin.models import BaseModelMixin

if TYPE_CHECKING:
    from app.modules.user.models import User


class RefreshToken(BaseModelMixin, SQLModel, table=True):
    """刷新令牌（登录后签发，用于换取新的访问令牌）"""

    __tablename__ = "refresh_token"

    user: User = Relationship(back_populates="refresh_tokens")

    token_hash: str = Field(
        unique=True,
        index=True,
        max_length=64,
        nullable=False,
        title="令牌哈希",
        description="SHA-256 十六进制摘要，不存储明文",
    )
    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        index=True,
        nullable=False,
        title="所属用户",
        description="令牌关联的用户 UUID",
    )
    expires_at: datetime = Field(
        index=True,
        nullable=False,
        title="过期时间",
        description="令牌过期时间，过期后不可再用于刷新",
    )
    revoked_at: datetime | None = Field(
        default=None,
        index=True,
        title="撤销时间",
        description="登出或旋转后置为当前时间，置空表示仍有效",
    )
