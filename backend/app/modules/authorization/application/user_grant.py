"""授权模块：用户授权应用服务

负责「用户 → 角色」与「用户 → 权限（直授）」的查询、分配与撤销，
以及当前用户有效权限查询。用户有效权限 = 角色授予 ∪ 直授允许 − 直授拒绝。
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
    add_user_role,
    delete_user_permission,
    delete_user_role,
    get_user_role,
    list_role_permission_codes,
    list_user_allowed_permission_codes,
    list_user_denied_permission_codes,
    list_user_roles,
    replace_user_allowed_permissions,
    replace_user_denied_permissions,
)
from app.modules.authorization.schemas import (
    MyPermissionsPublic,
    UserDeniedPermissionsUpdate,
    UserPermissionsPublic,
    UserPermissionsUpdate,
    UserRolesPublic,
)
from app.modules.permission.repositories.permission import list_permissions_by_ids
from app.modules.role.repositories.role import get_role_or_404
from app.modules.role.schemas import to_role_public
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


def _ensure_codes_in_operator_scope(
    *,
    session: Session,
    target_codes: set[str],
    operator: User,
    detail: str,
) -> None:
    """防提权 / 防越权剥夺：非超管的操作范围不能超过自身权限码"""
    operator_codes = get_user_permission_codes(session=session, user=operator)
    if not can_grant_permission_codes(
        operator_is_superuser=operator.is_superuser,
        operator_codes=operator_codes,
        target_codes=target_codes,
    ):
        raise HTTPException(status_code=403, detail=detail)


def _build_user_permissions(
    *, session: Session, user_id: uuid.UUID
) -> UserPermissionsPublic:
    """读取用户直授权限现状（直接授予 + 显式拒绝）"""
    return UserPermissionsPublic(
        user_id=user_id,
        allow_codes=sorted(
            list_user_allowed_permission_codes(session=session, user_id=user_id)
        ),
        deny_codes=sorted(
            list_user_denied_permission_codes(session=session, user_id=user_id)
        ),
    )


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
    """当前用户有效权限码：超管返回全部有效权限码，便于前端统一渲染"""
    codes = get_user_permission_codes(session=session, user=user)
    return MyPermissionsPublic(
        is_superuser=user.is_superuser,
        permission_codes=sorted(codes),
    )


def get_user_permissions(
    *, session: Session, user_id: uuid.UUID
) -> UserPermissionsPublic:
    """用户直授权限：直接授予（allow）与显式拒绝（deny），不含角色授予"""
    _get_target_user_or_404(session=session, user_id=user_id)
    return _build_user_permissions(session=session, user_id=user_id)


def set_user_permissions(
    *,
    session: Session,
    user_id: uuid.UUID,
    permission_in: UserPermissionsUpdate,
    operator: User,
) -> UserPermissionsPublic:
    """全量设置用户直授权限

    - 校验权限均存在且有效；
    - 非超管只能直授自己已持有的权限码（防提权）；
    - 目标权限上已存在的拒绝记录会被覆盖（同一权限不并存两种效果）；
    - 提交后立即失效该用户的权限缓存。
    """
    target_user = _get_target_user_or_404(session=session, user_id=user_id)
    rows = list_permissions_by_ids(
        session=session, permission_ids=permission_in.permission_ids
    )
    if len(rows) != len(set(permission_in.permission_ids)):
        raise HTTPException(status_code=422, detail="存在无效或已停用的权限")

    target_codes = {permission.code for permission, _category in rows}
    _ensure_codes_in_operator_scope(
        session=session,
        target_codes=target_codes,
        operator=operator,
        detail="不能授予超出自身权限范围的权限",
    )

    before_codes = sorted(
        list_user_allowed_permission_codes(session=session, user_id=user_id)
    )
    replace_user_allowed_permissions(
        session=session,
        user_id=user_id,
        permission_ids=[permission.id for permission, _category in rows],
        created_by=operator.id,
    )
    session.commit()
    invalidate_user_permissions(user_ids=[user_id])
    record_audit_log(
        session=session,
        actor=operator,
        action="user.assign_permission",
        resource_type="user",
        resource_id=str(target_user.id),
        before={"permission_codes": before_codes},
        after={"permission_codes": sorted(target_codes)},
    )
    return _build_user_permissions(session=session, user_id=user_id)


def set_user_denied_permissions(
    *,
    session: Session,
    user_id: uuid.UUID,
    permission_in: UserDeniedPermissionsUpdate,
    operator: User,
) -> UserPermissionsPublic:
    """全量设置用户直授拒绝（deny）

    - 校验权限均存在且有效；
    - 非超管只能拒绝自己已持有的权限码（防越权剥夺他人权限）；
    - 被拒绝的权限即使来自角色授予也会从有效权限中扣除；
    - 提交后立即失效该用户的权限缓存。
    """
    target_user = _get_target_user_or_404(session=session, user_id=user_id)
    rows = list_permissions_by_ids(
        session=session, permission_ids=permission_in.permission_ids
    )
    if len(rows) != len(set(permission_in.permission_ids)):
        raise HTTPException(status_code=422, detail="存在无效或已停用的权限")

    target_codes = {permission.code for permission, _category in rows}
    _ensure_codes_in_operator_scope(
        session=session,
        target_codes=target_codes,
        operator=operator,
        detail="不能拒绝超出自身权限范围的权限",
    )

    before_codes = sorted(
        list_user_denied_permission_codes(session=session, user_id=user_id)
    )
    replace_user_denied_permissions(
        session=session,
        user_id=user_id,
        permission_ids=[permission.id for permission, _category in rows],
        created_by=operator.id,
    )
    session.commit()
    invalidate_user_permissions(user_ids=[user_id])
    record_audit_log(
        session=session,
        actor=operator,
        action="user.deny_permission",
        resource_type="user",
        resource_id=str(target_user.id),
        before={"permission_codes": before_codes},
        after={"permission_codes": sorted(target_codes)},
    )
    return _build_user_permissions(session=session, user_id=user_id)


def remove_user_permission(
    *,
    session: Session,
    user_id: uuid.UUID,
    permission_id: uuid.UUID,
    operator: User,
) -> None:
    """撤销某权限上的用户直授记录（允许与拒绝一并清除，幂等）"""
    target_user = _get_target_user_or_404(session=session, user_id=user_id)
    rows = list_permissions_by_ids(session=session, permission_ids=[permission_id])
    if not rows:
        raise HTTPException(status_code=404, detail="权限不存在")
    permission = rows[0][0]

    delete_user_permission(
        session=session, user_id=user_id, permission_id=permission.id
    )
    session.commit()
    invalidate_user_permissions(user_ids=[user_id])
    record_audit_log(
        session=session,
        actor=operator,
        action="user.remove_permission",
        resource_type="user",
        resource_id=str(target_user.id),
        before={"permission_codes": [permission.code]},
    )
