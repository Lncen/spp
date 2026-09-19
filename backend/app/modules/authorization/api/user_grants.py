"""授权模块：用户授权接口（用户 → 角色、用户 → 权限）"""

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, SessionDep, require_permission
from app.common.models import Message
from app.modules.authorization.application.user_grant import (
    assign_role,
    get_my_permissions,
    get_user_permissions,
    get_user_roles,
    remove_role,
    remove_user_permission,
    set_user_denied_permissions,
    set_user_permissions,
)
from app.modules.authorization.schemas import (
    MyPermissionsPublic,
    UserDeniedPermissionsUpdate,
    UserPermissionsPublic,
    UserPermissionsUpdate,
    UserRoleAssign,
    UserRolesPublic,
)

user_grant_router = APIRouter(prefix="/users", tags=["roles"])


@user_grant_router.get("/me/permissions", response_model=MyPermissionsPublic)
def read_my_permissions(
    session: SessionDep, current_user: CurrentUser
) -> MyPermissionsPublic:
    """当前用户权限码（登录即可访问，供前端渲染菜单与按钮）"""
    return get_my_permissions(session=session, user=current_user)


@user_grant_router.get(
    "/{user_id}/roles",
    response_model=UserRolesPublic,
    dependencies=[Depends(require_permission("role:view"))],
)
def read_user_roles(*, session: SessionDep, user_id: uuid.UUID) -> UserRolesPublic:
    """用户已分配角色"""
    return get_user_roles(session=session, user_id=user_id)


@user_grant_router.post(
    "/{user_id}/roles",
    response_model=UserRolesPublic,
    dependencies=[Depends(require_permission("role:assign_user"))],
)
def assign_user_role(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    user_id: uuid.UUID,
    role_in: UserRoleAssign,
) -> UserRolesPublic:
    """为用户分配角色"""
    return assign_role(
        session=session,
        user_id=user_id,
        role_id=role_in.role_id,
        operator=current_user,
    )


@user_grant_router.delete(
    "/{user_id}/roles/{role_id}",
    response_model=Message,
    dependencies=[Depends(require_permission("role:assign_user"))],
)
def remove_user_role(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
) -> Message:
    """移除用户角色"""
    remove_role(
        session=session,
        user_id=user_id,
        role_id=role_id,
        operator=current_user,
    )
    return Message(message="角色已移除")


@user_grant_router.get(
    "/{user_id}/permissions",
    response_model=UserPermissionsPublic,
    dependencies=[Depends(require_permission("user:view"))],
)
def read_user_permissions(
    *, session: SessionDep, user_id: uuid.UUID
) -> UserPermissionsPublic:
    """用户直授权限：直接授予（allow）与显式拒绝（deny）"""
    return get_user_permissions(session=session, user_id=user_id)


@user_grant_router.put(
    "/{user_id}/permissions",
    response_model=UserPermissionsPublic,
    dependencies=[Depends(require_permission("user:assign_permission"))],
)
def set_user_permissions_endpoint(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    user_id: uuid.UUID,
    permission_in: UserPermissionsUpdate,
) -> UserPermissionsPublic:
    """全量设置用户直授权限"""
    return set_user_permissions(
        session=session,
        user_id=user_id,
        permission_in=permission_in,
        operator=current_user,
    )


@user_grant_router.put(
    "/{user_id}/permissions/deny",
    response_model=UserPermissionsPublic,
    dependencies=[Depends(require_permission("user:assign_permission"))],
)
def set_user_denied_permissions_endpoint(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    user_id: uuid.UUID,
    permission_in: UserDeniedPermissionsUpdate,
) -> UserPermissionsPublic:
    """全量设置用户直授拒绝权限（deny 优先于角色授予与直授允许）"""
    return set_user_denied_permissions(
        session=session,
        user_id=user_id,
        permission_in=permission_in,
        operator=current_user,
    )


@user_grant_router.delete(
    "/{user_id}/permissions/{permission_id}",
    response_model=Message,
    dependencies=[Depends(require_permission("user:assign_permission"))],
)
def remove_user_permission_endpoint(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    user_id: uuid.UUID,
    permission_id: uuid.UUID,
) -> Message:
    """撤销某权限上的用户直授记录（允许与拒绝一并清除）"""
    remove_user_permission(
        session=session,
        user_id=user_id,
        permission_id=permission_id,
        operator=current_user,
    )
    return Message(message="权限已移除")
