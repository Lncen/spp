"""权限定义模块：只读接口

权限定义由系统初始化脚本写入，这里不提供任何写接口。
三个接口统一要求 ``permission:view`` 权限，权限校验声明在路由层。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, require_permission
from app.modules.permission.application.permission_query import (
    get_permission_categories,
    get_permission_tree,
    get_permissions,
)
from app.modules.permission.domain.catalog import ActionType
from app.modules.permission.schemas import (
    PermissionCategoriesPublic,
    PermissionsPublic,
    PermissionTreePublic,
)

router = APIRouter(
    tags=["permissions"],
    dependencies=[Depends(require_permission("permission:view"))],
)


@router.get("/permission-categories", response_model=PermissionCategoriesPublic)
def read_permission_categories(session: SessionDep) -> PermissionCategoriesPublic:
    """权限分类列表"""
    return get_permission_categories(session=session)


@router.get("/permissions/tree", response_model=PermissionTreePublic)
def read_permission_tree(session: SessionDep) -> PermissionTreePublic:
    """权限树（分类 + 权限），供角色授权界面使用"""
    return get_permission_tree(session=session)


@router.get("/permissions", response_model=PermissionsPublic)
def read_permissions(
    session: SessionDep,
    action: Annotated[ActionType | None, Query()] = None,
) -> PermissionsPublic:
    """权限列表，可按动作类型过滤"""
    return get_permissions(session=session, action=action)
