"""授权模块：角色权限关联模型

``role_permission`` 表示「角色 → 权限」的授予关系，
与 ``user_role``、``user_permission`` 同属授权关系，不归角色或权限定义所有。
"""

import uuid

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin


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
