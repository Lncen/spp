"""角色模块：角色定义接口

角色授权（角色 → 权限）与用户角色分配见 authorization 模块的接口。
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, SessionDep, require_permission
from app.common.models import Message
from app.modules.role.application.role_management import (
    create_role,
    delete_role,
    get_role_detail,
    get_roles_page,
    update_role,
)
from app.modules.role.schemas import RoleCreate, RolePublic, RolesPublic, RoleUpdate

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
