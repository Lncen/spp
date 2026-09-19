"""授权模块：用户角色关联模型"""

import uuid

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.mixin.models import AuditUserMixin, BaseModelMixin


class UserRole(BaseModelMixin, AuditUserMixin, SQLModel, table=True):
    """用户角色关联"""

    __tablename__ = "user_role"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role_user_role"),
    )

    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
        title="用户 ID",
        description="关联用户的 UUID",
    )
    role_id: uuid.UUID = Field(
        foreign_key="role.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
        title="角色 ID",
        description="关联角色的 UUID",
    )
