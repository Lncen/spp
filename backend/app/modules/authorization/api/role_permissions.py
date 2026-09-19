"""授权模块：角色授权接口（角色 → 权限）"""

import uuid

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, SessionDep, require_permission
from app.modules.authorization.application.role_grant import (
    get_role_permissions,
    set_role_permissions,
)
from app.modules.authorization.schemas import (
    RolePermissionsPublic,
    RolePermissionsUpdate,
)

role_permission_router = APIRouter(prefix="/roles", tags=["roles"])


@role_permission_router.get(
    "/{role_id}/permissions",
    response_model=RolePermissionsPublic,
    dependencies=[Depends(require_permission("role:view"))],
)
def read_role_permissions(
    *, session: SessionDep, role_id: uuid.UUID
) -> RolePermissionsPublic:
    """角色已持有的权限码"""
    return get_role_permissions(session=session, role_id=role_id)


@role_permission_router.put(
    "/{role_id}/permissions",
    response_model=RolePermissionsPublic,
    dependencies=[Depends(require_permission("role:assign_permission"))],
)
def set_role_permissions_endpoint(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    role_id: uuid.UUID,
    permission_in: RolePermissionsUpdate,
) -> RolePermissionsPublic:
    """全量设置角色权限"""
    return set_role_permissions(
        session=session,
        role_id=role_id,
        permission_in=permission_in,
        operator=current_user,
    )
