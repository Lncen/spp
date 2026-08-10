import uuid
from typing import TYPE_CHECKING

from pydantic import EmailStr
from sqlalchemy import Column, ForeignKey, Uuid
from sqlmodel import Field, Relationship, SQLModel

from app.core.mixin.models import BaseModelMixin

if TYPE_CHECKING:
    from app.modules.auth.models import RefreshToken
    from app.modules.image.models import Image
    from app.modules.item.models import Item


class User(BaseModelMixin, SQLModel, table=True):
    """用户数据库模型"""

    level_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="user_level.id",
        nullable=True,
        title="用户等级",
        description="关联的用户等级 UUID",
    )

    username: str = Field(
        unique=True,
        index=True,
        max_length=255,
        title="用户名",
        description="用户登录名，必须唯一且长度不超过255个字符",
    )

    email: EmailStr = Field(
        unique=True,
        index=True,
        max_length=255,
        title="电子邮箱",
        description="用户的登录邮箱，必须唯一且长度不超过255个字符",
    )

    is_superuser: bool = Field(
        default=False,
        title="超级管理员",
        description="标识该用户是否拥有超级管理员权限，默认为否",
    )

    full_name: str | None = Field(
        default=None,
        max_length=255,
        title="用户昵称",
        description="用户的昵称姓名或显示名称，选填，长度不超过255个字符",
    )

    can_order: bool = Field(
        default=True,
        index=True,
        title="是否允许下单",
        description="独立控制用户是否可创建订单，与账号启用状态互不影响",
    )

    avatar_id: uuid.UUID | None = Field(
        default=None,
        sa_column=Column(
            Uuid(),
            ForeignKey("image.id", ondelete="SET NULL", use_alter=True),
            nullable=True,
        ),
        title="用户头像",
        description="用户头像图片 ID，关联 image 表；图片删除时自动置空",
    )

    remark: str | None = Field(
        default=None,
        max_length=255,
        title="备注",
        description="管理员对用户的备注，仅管理员可修改",
    )

    bio: str | None = Field(
        default=None,
        max_length=1000,
        title="简介",
        description="用户个人简介，由用户自己维护",
    )

    hashed_password: str = Field(
        title="加密密码",
        description="经过哈希处理后的用户密码，用于安全验证，禁止明文存储",
    )

    # 关系字段不需要也不支持 Field 参数，保持原样即可
    items: list[Item] = Relationship(back_populates="owner", cascade_delete=True)
    images: list[Image] = Relationship(
        back_populates="owner",
        cascade_delete=True,
        sa_relationship_kwargs={"foreign_keys": "Image.owner_id"},
    )
    refresh_tokens: list[RefreshToken] = Relationship(
        back_populates="user", cascade_delete=True
    )
