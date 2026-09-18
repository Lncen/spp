"""角色模块：角色管理应用服务

负责流程编排：校验 → 写库 → 提交 → 缓存失效 → 审计。
"""

import uuid
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.permission.repositories.permission import list_permissions_by_ids
from app.modules.role.application.permission_check import get_user_permission_codes
from app.modules.role.domain.authorization import can_grant_permission_codes
from app.modules.role.infrastructure.cache import invalidate_user_permissions
from app.modules.role.models import Role
from app.modules.role.repositories.role import (
    count_roles,
    create_role_row,
    delete_role_row,
    get_role_by_code,
    get_role_or_404,
    list_role_permission_codes,
    list_roles,
    list_user_ids_by_role,
    replace_role_permissions,
)
from app.modules.role.schemas import (
    RoleCreate,
    RolePermissionsPublic,
    RolePermissionsUpdate,
    RolePublic,
    RolesPublic,
    RoleUpdate,
)
from app.modules.system_log.application.audit_log_create import record_audit_log
from app.modules.user.models import User

# 自动生成角色码的重试次数：角色码为系统内部字段，无需用户填写
_ROLE_CODE_MAX_ATTEMPTS = 5


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


def _operator_permission_codes(*, session: Session, operator: User) -> set[str]:
    """操作者当前持有的权限码，用于防提权校验"""
    return get_user_permission_codes(session=session, user=operator)


def get_roles_page(
    *, session: Session, skip: int, limit: int, keyword: str | None = None
) -> RolesPublic:
    """角色分页列表"""
    total = count_roles(session=session, keyword=keyword)
    rows = list_roles(session=session, skip=skip, limit=limit, keyword=keyword)
    return RolesPublic(count=total, data=[to_role_public(role=row) for row in rows])


def get_role_detail(*, session: Session, role_id: uuid.UUID) -> RolePublic:
    """角色详情"""
    return to_role_public(role=get_role_or_404(session=session, role_id=role_id))


def _resolve_role_code(*, session: Session, code: str | None) -> str:
    """确定角色码

    - 显式传入：校验未被占用，冲突返回 409；
    - 未传入：自动生成 ``role_<12 位十六进制>``，管理端无需填写。
    """
    if code is not None:
        if get_role_by_code(session=session, code=code) is not None:
            raise HTTPException(status_code=409, detail="角色码已存在")
        return code

    for _ in range(_ROLE_CODE_MAX_ATTEMPTS):
        generated = f"role_{uuid.uuid4().hex[:12]}"
        if get_role_by_code(session=session, code=generated) is None:
            return generated
    raise HTTPException(status_code=409, detail="角色码生成失败，请重试")


def get_role_permissions(
    *, session: Session, role_id: uuid.UUID
) -> RolePermissionsPublic:
    """角色权限码列表"""
    role = get_role_or_404(session=session, role_id=role_id)
    return RolePermissionsPublic(
        role_id=role.id,
        permission_codes=sorted(
            list_role_permission_codes(session=session, role_id=role.id)
        ),
    )


def create_role(
    *, session: Session, role_in: RoleCreate, operator: User
) -> RolePublic:
    """创建自定义角色"""
    code = _resolve_role_code(session=session, code=role_in.code)
    role = create_role_row(
        session=session,
        code=code,
        name=role_in.name,
        description=role_in.description,
        sort_order=role_in.sort_order,
        is_system=False,
        created_by=operator.id,
    )
    session.commit()
    session.refresh(role)
    record_audit_log(
        session=session,
        actor=operator,
        action="创建角色",
        resource_type="role",
        resource_id=role.code,
        after={"code": role.code, "name": role.name},
    )
    return to_role_public(role=role)


def update_role(
    *,
    session: Session,
    role_id: uuid.UUID,
    role_in: RoleUpdate,
    operator: User,
) -> RolePublic:
    """修改角色；系统内置角色仅超管可改，且不可停用"""
    role = get_role_or_404(session=session, role_id=role_id)
    if role.is_system:
        if not operator.is_superuser:
            raise HTTPException(status_code=403, detail="系统内置角色仅超级管理员可修改")
        if role_in.is_active is False:
            raise HTTPException(status_code=400, detail="系统内置角色不可停用")

    before: dict[str, Any] = {
        "name": role.name,
        "description": role.description,
        "sort_order": role.sort_order,
        "is_active": role.is_active,
    }
    changed: dict[str, Any] = {}
    for field, value in (
        ("name", role_in.name),
        ("description", role_in.description),
        ("sort_order", role_in.sort_order),
        ("is_active", role_in.is_active),
    ):
        if value is not None and getattr(role, field) != value:
            changed[field] = {"old": getattr(role, field), "new": value}
            setattr(role, field, value)

    if not changed:
        return to_role_public(role=role)

    role.updated_by = operator.id
    session.add(role)
    session.commit()
    session.refresh(role)

    if "is_active" in changed:
        # 角色停用后其用户权限立即失效
        invalidate_user_permissions(
            user_ids=list_user_ids_by_role(session=session, role_id=role.id)
        )
    record_audit_log(
        session=session,
        actor=operator,
        action="更新角色",
        resource_type="role",
        resource_id=role.code,
        before=before,
        after={
            "name": role.name,
            "description": role.description,
            "sort_order": role.sort_order,
            "is_active": role.is_active,
        },
        changes=changed,
    )
    return to_role_public(role=role)


def delete_role(*, session: Session, role_id: uuid.UUID, operator: User) -> None:
    """删除自定义角色

    - 系统内置角色禁止删除；
    - 同时清理角色权限与用户角色关联，避免留下悬挂关系；
    - 提交后失效受影响用户的权限缓存，并写入审计。
    """
    role = get_role_or_404(session=session, role_id=role_id)
    if role.is_system:
        raise HTTPException(status_code=400, detail="系统内置角色不可删除")

    snapshot: dict[str, Any] = {
        "code": role.code,
        "name": role.name,
        "description": role.description,
        "is_system": role.is_system,
        "permission_codes": sorted(
            list_role_permission_codes(session=session, role_id=role.id)
        ),
    }
    affected_user_ids = list_user_ids_by_role(session=session, role_id=role.id)

    delete_role_row(session=session, role=role)
    session.commit()

    invalidate_user_permissions(user_ids=affected_user_ids)
    record_audit_log(
        session=session,
        actor=operator,
        action="删除角色",
        resource_type="role",
        resource_id=snapshot["code"],
        before=snapshot,
    )


def set_role_permissions(
    *,
    session: Session,
    role_id: uuid.UUID,
    permission_in: RolePermissionsUpdate,
    operator: User,
) -> RolePermissionsPublic:
    """全量设置角色权限

    - 校验权限均存在且有效；
    - 非超管只能授予自己已持有的权限码（防提权）；
    - 提交后立即失效该角色下全部用户的权限缓存。
    """
    role = get_role_or_404(session=session, role_id=role_id)
    rows = list_permissions_by_ids(
        session=session, permission_ids=permission_in.permission_ids
    )
    if len(rows) != len(set(permission_in.permission_ids)):
        raise HTTPException(status_code=422, detail="存在无效或已停用的权限")

    target_codes = {permission.code for permission, _category in rows}
    operator_codes = _operator_permission_codes(session=session, operator=operator)
    if not can_grant_permission_codes(
        operator_is_superuser=operator.is_superuser,
        operator_codes=operator_codes,
        target_codes=target_codes,
    ):
        raise HTTPException(status_code=403, detail="不能授予超出自身权限范围的权限")

    before_codes = sorted(
        list_role_permission_codes(session=session, role_id=role.id)
    )
    affected_user_ids = list_user_ids_by_role(session=session, role_id=role.id)
    replace_role_permissions(
        session=session,
        role_id=role.id,
        permission_ids=[permission.id for permission, _category in rows],
        created_by=operator.id,
    )
    session.commit()
    invalidate_user_permissions(user_ids=affected_user_ids)
    record_audit_log(
        session=session,
        actor=operator,
        action="分配权限",
        resource_type="role",
        resource_id=role.code,
        before={"permission_codes": before_codes},
        after={"permission_codes": sorted(target_codes)},
    )
    return RolePermissionsPublic(
        role_id=role.id,
        permission_codes=sorted(target_codes),
    )
