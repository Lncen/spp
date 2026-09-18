"""角色模块：用户角色分配应用服务"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.role.application.permission_check import get_user_permission_codes
from app.modules.role.application.role_management import to_role_public
from app.modules.role.domain.authorization import can_grant_permission_codes
from app.modules.role.infrastructure.cache import invalidate_user_permissions
from app.modules.role.repositories.role import (
    add_user_role,
    delete_user_role,
    get_role_or_404,
    get_user_role,
    list_role_permission_codes,
    list_user_roles,
)
from app.modules.role.schemas import MyPermissionsPublic, UserRolesPublic
from app.modules.system_log.application.audit_log_create import record_audit_log
from app.modules.user.application.user_query import get_user_by_id
from app.modules.user.models import User


def _get_target_user_or_404(*, session: Session, user_id: uuid.UUID) -> User:
    """查询目标用户，不存在时抛出 404"""
    user = get_user_by_id(session=session, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


def _ensure_can_assign_role(
    *, session: Session, role_id: uuid.UUID, operator: User
) -> None:
    """防提权：非超管只能分配权限范围不超过自身的角色"""
    role_codes = list_role_permission_codes(session=session, role_id=role_id)
    operator_codes = get_user_permission_codes(session=session, user=operator)
    if not can_grant_permission_codes(
        operator_is_superuser=operator.is_superuser,
        operator_codes=operator_codes,
        target_codes=role_codes,
    ):
        raise HTTPException(status_code=403, detail="不能分配超出自身权限范围的角色")


def get_user_roles(*, session: Session, user_id: uuid.UUID) -> UserRolesPublic:
    """用户已分配角色"""
    _get_target_user_or_404(session=session, user_id=user_id)
    rows = list_user_roles(session=session, user_id=user_id)
    return UserRolesPublic(
        count=len(rows), data=[to_role_public(role=row) for row in rows]
    )


def assign_role(
    *,
    session: Session,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    operator: User,
) -> UserRolesPublic:
    """为用户分配角色（幂等：已分配则直接返回当前角色列表）"""
    target_user = _get_target_user_or_404(session=session, user_id=user_id)
    role = get_role_or_404(session=session, role_id=role_id)
    if not role.is_active:
        raise HTTPException(status_code=400, detail="角色已停用")
    _ensure_can_assign_role(session=session, role_id=role.id, operator=operator)

    if get_user_role(session=session, user_id=user_id, role_id=role.id) is None:
        add_user_role(
            session=session,
            user_id=user_id,
            role_id=role.id,
            created_by=operator.id,
        )
        session.commit()
        invalidate_user_permissions(user_ids=[user_id])
        record_audit_log(
            session=session,
            actor=operator,
            action="user.assign_role",
            resource_type="user",
            resource_id=str(target_user.id),
            after={"role_code": role.code},
        )
    return get_user_roles(session=session, user_id=user_id)


def remove_role(
    *,
    session: Session,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    operator: User,
) -> None:
    """移除用户角色（幂等）"""
    target_user = _get_target_user_or_404(session=session, user_id=user_id)
    role = get_role_or_404(session=session, role_id=role_id)
    if get_user_role(session=session, user_id=user_id, role_id=role.id) is not None:
        delete_user_role(session=session, user_id=user_id, role_id=role.id)
        session.commit()
        invalidate_user_permissions(user_ids=[user_id])
        record_audit_log(
            session=session,
            actor=operator,
            action="user.remove_role",
            resource_type="user",
            resource_id=str(target_user.id),
            before={"role_code": role.code},
        )


def get_my_permissions(*, session: Session, user: User) -> MyPermissionsPublic:
    """当前用户权限码：超管返回全部有效权限码，便于前端统一渲染"""
    codes = get_user_permission_codes(session=session, user=user)
    return MyPermissionsPublic(
        is_superuser=user.is_superuser,
        permission_codes=sorted(codes),
    )
