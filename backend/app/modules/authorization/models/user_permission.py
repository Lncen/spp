"""授权模块：用户直授权限模型

``user_permission`` 表示「用户 → 权限」的直接授权，独立于角色授予：

用户有效权限 = 角色授予 ∪ 直授允许 − 直授拒绝

``effect`` 区分直接授予（allow）与显式拒绝（deny），拒绝会从有效权限中扣除；
账号停用仍由授权判定统一拒绝。
"""

import uuid

from sqlalchemy import String, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.core.mixin.models import AuditUserMixin, BaseModelMixin
from app.modules.authorization.domain.authorization import GrantEffect


class UserPermission(BaseModelMixin, AuditUserMixin, SQLModel, table=True):
    """用户直授权限关联"""

    __tablename__ = "user_permission"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "permission_id",
            name="uq_user_permission_user_permission",
        ),
    )

    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
        title="用户 ID",
        description="关联用户的 UUID",
    )
    permission_id: uuid.UUID = Field(
        foreign_key="permission.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
        title="权限 ID",
        description="关联权限定义的 UUID",
    )
    effect: GrantEffect = Field(
        sa_type=String(8),
        default=GrantEffect.ALLOW,
        nullable=False,
        title="授权效果",
        description="allow 直接授予 / deny 显式拒绝，拒绝从有效权限中扣除",
    )
