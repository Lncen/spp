"""角色模块：请求与响应模型

``to_role_public`` 是角色 ORM → 对外 DTO 的唯一转换入口，
授权模块返回用户角色列表时复用，避免重复映射逻辑。
"""

import re
import uuid
from datetime import datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.modules.role.models import Role


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


def to_role_public(*, role: Role) -> RolePublic:
    """角色 ORM → 对外 DTO"""
    return RolePublic(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        sort_order=role.sort_order,
        is_system=role.is_system,
        is_active=role.is_active,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )
