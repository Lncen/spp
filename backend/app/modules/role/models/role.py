"""角色模块：数据模型

- ``role``：角色定义；角色与权限、角色与用户的授予关系见 authorization 模块。
"""

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
