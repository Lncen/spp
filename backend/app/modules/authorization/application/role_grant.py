"""授权模块：角色授权应用服务

负责「角色 → 权限」的查询与全量设置，并向角色模块提供角色删除 / 停用所需的
授权清理入口（跨模块只暴露 application 层函数，避免角色模块直接访问授权表）。
"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.authorization.application.permission_check import (
    get_user_permission_codes,
)
from app.modules.authorization.domain.authorization import can_grant_permission_codes
from app.modules.authorization.infrastructure.cache import invalidate_user_permissions
from app.modules.authorization.repositories.grant import (
    delete_role_grants,
    list_role_permission_codes,
    list_user_ids_by_role,
    replace_role_permissions,
)
from app.modules.authorization.schemas import (
    RolePermissionsPublic,
    RolePermissionsUpdate,
)
from app.modules.permission.repositories.permission import list_permissions_by_ids
from app.modules.role.repositories.role import get_role_or_404
from app.modules.system_log.application.audit_log_create import record_audit_log
from app.modules.user.models import User


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
    operator_codes = get_user_permission_codes(session=session, user=operator)
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


def list_role_user_ids(*, session: Session, role_id: uuid.UUID) -> list[uuid.UUID]:
    """持有该角色的用户 ID，供角色停用后失效其权限缓存"""
    return list_user_ids_by_role(session=session, role_id=role_id)


def remove_role_grants(*, session: Session, role_id: uuid.UUID) -> list[uuid.UUID]:
    """删除角色的权限授权与用户角色分配（不提交），返回受影响用户 ID"""
    return delete_role_grants(session=session, role_id=role_id)
