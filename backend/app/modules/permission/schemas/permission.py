"""权限定义模块：响应模型"""

from uuid import UUID

from sqlmodel import SQLModel

from app.modules.permission.domain.catalog import ActionType


class PermissionCategoryPublic(SQLModel):
    """权限分类"""

    id: UUID
    name: str
    description: str | None
    sort_order: int
    is_active: bool


class PermissionPublic(SQLModel):
    """权限项，``code`` 为权限码，``action`` 为动作类型"""

    id: UUID
    code: str
    category_id: UUID
    category_name: str
    action: ActionType
    name: str
    description: str | None
    sort_order: int
    is_active: bool


class PermissionCategoriesPublic(SQLModel):
    """权限分类列表响应"""

    count: int
    data: list[PermissionCategoryPublic]


class PermissionsPublic(SQLModel):
    """权限列表响应"""

    count: int
    data: list[PermissionPublic]


class PermissionTreeCategory(SQLModel):
    """权限树节点：分类及其权限"""

    id: UUID
    name: str
    description: str | None
    sort_order: int
    permissions: list[PermissionPublic]


class PermissionTreePublic(SQLModel):
    """权限树响应，供角色授权界面使用"""

    count: int
    data: list[PermissionTreeCategory]
