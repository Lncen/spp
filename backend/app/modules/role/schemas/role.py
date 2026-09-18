"""角色模块：请求与响应模型"""

import re
import uuid
from datetime import datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel


class RoleCreate(SQLModel):
    """创建角色请求

    ``code`` 为系统内部字段：不传时由服务端自动生成，管理端无需填写。
    """

    code: str | None = Field(default=None, max_length=64)
    name: str = Field(max_length=128)
    description: str | None = Field(default=None, max_length=255)
    sort_order: int = 0

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str | None) -> str | None:
        """角色码统一小写，只允许字母、数字与下划线"""
        if value is None:
            return None
        normalized = value.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", normalized):
            raise ValueError("角色码只能包含小写字母、数字与下划线，且以字母开头")
        return normalized

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("角色名称不能为空")
        return value.strip()


class RoleUpdate(SQLModel):
    """修改角色请求，仅提交需要变更的字段"""

    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=255)
    sort_order: int | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("角色名称不能为空")
        return value.strip() if value is not None else None


class RolePublic(SQLModel):
    """角色对外展示结构"""

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    sort_order: int
    is_system: bool
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None


class RolesPublic(SQLModel):
    """角色列表响应"""

    count: int
    data: list[RolePublic]


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
