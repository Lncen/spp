"""角色模块：数据模型

- ``role``：角色定义；
- ``role_permission``：角色与权限定义的关联；
- ``user_role``：用户与角色的关联。
"""

import uuid

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.mixin.models import AuditUserMixin, BaseModelMixin


class Role(BaseModelMixin, AuditUserMixin, SQLModel, table=True):
    """角色"""

    __tablename__ = "role"

    code: str = Field(
        unique=True,
        index=True,
        max_length=64,
        nullable=False,
        title="角色码",
        description="全局唯一标识，如 admin / order_operator",
    )
    name: str = Field(
        max_length=128,
        nullable=False,
        title="角色名称",
        description="管理界面展示的角色名称",
    )
    description: str | None = Field(
        default=None,
        max_length=255,
        title="角色说明",
        description="角色职责说明",
    )
    sort_order: int = Field(
        default=0,
        index=True,
        title="排序",
        description="管理界面展示顺序，越小越靠前",
    )
    is_system: bool = Field(
        default=False,
        index=True,
        title="系统内置角色",
        description="系统内置角色不可删除、不可停用，由初始化脚本维护",
    )


class RolePermission(BaseModelMixin, SQLModel, table=True):
    """角色权限关联"""

    __tablename__ = "role_permission"
    __table_args__ = (
        UniqueConstraint(
            "role_id",
            "permission_id",
            name="uq_role_permission_role_permission",
        ),
    )

    role_id: uuid.UUID = Field(
        foreign_key="role.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
        title="角色 ID",
        description="关联角色的 UUID",
    )
    permission_id: uuid.UUID = Field(
        foreign_key="permission.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
        title="权限 ID",
        description="关联权限定义的 UUID",
    )


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
