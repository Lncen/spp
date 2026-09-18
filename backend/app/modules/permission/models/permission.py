"""权限定义模块：数据模型

``permission_category`` 与 ``permission`` 只由系统初始化脚本写入，
管理端仅提供只读接口，运行期不提供写接口。

权限码直接存储在 ``permission.code`` 上，不由分类或动作拼接；
``permission.action`` 是动作类型，仅用于分组展示与筛选。
"""

import uuid

from sqlalchemy import String
from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin
from app.modules.permission.domain.catalog import ActionType


class PermissionCategory(BaseModelMixin, SQLModel, table=True):
    """权限分类：仅用于管理界面的分组展示"""

    __tablename__ = "permission_category"

    name: str = Field(
        unique=True,
        index=True,
        max_length=128,
        nullable=False,
        title="分类名称",
        description="管理界面展示的分类名称，如 角色管理",
    )
    description: str | None = Field(
        default=None,
        max_length=255,
        title="分类说明",
        description="分类职责说明",
    )
    sort_order: int = Field(
        default=0,
        index=True,
        title="排序",
        description="管理界面展示顺序，越小越靠前",
    )


class Permission(BaseModelMixin, SQLModel, table=True):
    """权限项：权限码与动作类型都由本表维护"""

    __tablename__ = "permission"

    code: str = Field(
        unique=True,
        index=True,
        max_length=128,
        nullable=False,
        title="权限码",
        description="可直接使用或做权限校验的完整权限码，如 role:view",
    )
    category_id: uuid.UUID = Field(
        foreign_key="permission_category.id",
        ondelete="CASCADE",
        index=True,
        nullable=False,
        title="分类 ID",
        description="所属权限分类 UUID，仅用于分组展示",
    )
    action: ActionType = Field(
        sa_type=String(32),
        nullable=False,
        index=True,
        title="动作类型",
        description="动作类型，如 view / create / update / manage",
    )
    name: str = Field(
        max_length=128,
        nullable=False,
        title="权限名称",
        description="管理界面展示的权限名称",
    )
    description: str | None = Field(
        default=None,
        max_length=255,
        title="权限说明",
        description="该权限允许的操作说明",
    )
    sort_order: int = Field(
        default=0,
        title="排序",
        description="同一分类内的展示顺序，越小越靠前",
    )
