"""角色模块：角色管理与用户角色分配接口"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, SessionDep, require_permission
from app.common.models import Message
from app.modules.role.application.role_management import (
    create_role,
    delete_role,
    get_role_detail,
    get_role_permissions,
    get_roles_page,
    set_role_permissions,
    update_role,
)
from app.modules.role.application.user_role_assignment import (
    assign_role,
    get_my_permissions,
    get_user_roles,
    remove_role,
)
from app.modules.role.schemas import (
    MyPermissionsPublic,
    RoleCreate,
    RolePermissionsPublic,
    RolePermissionsUpdate,
    RolePublic,
    RolesPublic,
    RoleUpdate,
    UserRoleAssign,
    UserRolesPublic,
)

role_router = APIRouter(prefix="/roles", tags=["roles"])


@role_router.get(
    "",
    response_model=RolesPublic,
    dependencies=[Depends(require_permission("role:view"))],
)
def read_roles(
    session: SessionDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    keyword: Annotated[str | None, Query(max_length=64)] = None,
) -> RolesPublic:
    """角色分页列表"""
    return get_roles_page(session=session, skip=skip, limit=limit, keyword=keyword)


@role_router.post(
    "",
    response_model=RolePublic,
    dependencies=[Depends(require_permission("role:create"))],
)
def create_role_endpoint(
    *, session: SessionDep, current_user: CurrentUser, role_in: RoleCreate
) -> RolePublic:
    """创建自定义角色"""
    return create_role(session=session, role_in=role_in, operator=current_user)


@role_router.get(
    "/{role_id}",
    response_model=RolePublic,
    dependencies=[Depends(require_permission("role:view"))],
)
def read_role(*, session: SessionDep, role_id: uuid.UUID) -> RolePublic:
    """角色详情"""
    return get_role_detail(session=session, role_id=role_id)


@role_router.patch(
    "/{role_id}",
    response_model=RolePublic,
    dependencies=[Depends(require_permission("role:update"))],
)
def update_role_endpoint(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    role_id: uuid.UUID,
    role_in: RoleUpdate,
) -> RolePublic:
    """修改角色名称、描述与启停状态"""
    return update_role(
        session=session,
        role_id=role_id,
        role_in=role_in,
        operator=current_user,
    )


@role_router.delete(
    "/{role_id}",
    response_model=Message,
    dependencies=[Depends(require_permission("role:delete"))],
)
def delete_role_endpoint(
    *, session: SessionDep, current_user: CurrentUser, role_id: uuid.UUID
) -> Message:
    """删除自定义角色（同时解除该角色下的用户分配）"""
    delete_role(session=session, role_id=role_id, operator=current_user)
    return Message(message="角色已删除")


@role_router.get(
    "/{role_id}/permissions",
    response_model=RolePermissionsPublic,
    dependencies=[Depends(require_permission("role:view"))],
)
def read_role_permissions(
    *, session: SessionDep, role_id: uuid.UUID
) -> RolePermissionsPublic:
    """角色已持有的权限码"""
    return get_role_permissions(session=session, role_id=role_id)


@role_router.put(
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


user_role_router = APIRouter(prefix="/users", tags=["roles"])


@user_role_router.get("/me/permissions", response_model=MyPermissionsPublic)
def read_my_permissions(
    session: SessionDep, current_user: CurrentUser
) -> MyPermissionsPublic:
    """当前用户权限码（登录即可访问，供前端渲染菜单与按钮）"""
    return get_my_permissions(session=session, user=current_user)


@user_role_router.get(
    "/{user_id}/roles",
    response_model=UserRolesPublic,
    dependencies=[Depends(require_permission("role:view"))],
)
def read_user_roles(*, session: SessionDep, user_id: uuid.UUID) -> UserRolesPublic:
    """用户已分配角色"""
    return get_user_roles(session=session, user_id=user_id)


@user_role_router.post(
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


@user_role_router.delete(
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
