"""授权模块：请求与响应模型"""

import uuid

from sqlmodel import SQLModel

from app.modules.role.schemas import RolePublic


class RolePermissionsUpdate(SQLModel):
    """设置角色权限请求：全量覆盖"""

    permission_ids: list[uuid.UUID]


class RolePermissionsPublic(SQLModel):
    """角色权限响应"""

    role_id: uuid.UUID
    permission_codes: list[str]


class UserRoleAssign(SQLModel):
    """为用户分配角色请求"""

    role_id: uuid.UUID


class UserRolesPublic(SQLModel):
    """用户角色列表响应"""

    count: int
    data: list[RolePublic]


class MyPermissionsPublic(SQLModel):
    """当前用户权限响应：超管返回全部有效权限码"""

    is_superuser: bool
    permission_codes: list[str]


class UserPermissionsUpdate(SQLModel):
    """设置用户直授权限请求：全量覆盖"""

    permission_ids: list[uuid.UUID]


class UserDeniedPermissionsUpdate(SQLModel):
    """设置用户直授拒绝请求：全量覆盖"""

    permission_ids: list[uuid.UUID]


class UserPermissionsPublic(SQLModel):
    """用户直授权限响应：直接授予与显式拒绝两类"""

    user_id: uuid.UUID
    allow_codes: list[str]
    deny_codes: list[str]
