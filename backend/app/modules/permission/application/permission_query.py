"""权限定义模块：只读查询应用服务"""

import uuid

from sqlmodel import Session

from app.modules.permission.domain.catalog import ActionType
from app.modules.permission.models import Permission, PermissionCategory
from app.modules.permission.repositories.permission import (
    list_active_permission_codes,
    list_categories,
    list_permissions,
)
from app.modules.permission.schemas import (
    PermissionCategoriesPublic,
    PermissionCategoryPublic,
    PermissionPublic,
    PermissionsPublic,
    PermissionTreeCategory,
    PermissionTreePublic,
)


def _to_permission_public(
    *, permission: Permission, category: PermissionCategory
) -> PermissionPublic:
    """把权限与分类拼装为对外 DTO，附带完整权限码"""
    return PermissionPublic(
        id=permission.id,
        code=permission.code,
        category_id=category.id,
        category_name=category.name,
        action=permission.action,
        name=permission.name,
        description=permission.description,
        sort_order=permission.sort_order,
        is_active=permission.is_active,
    )


def get_permission_categories(*, session: Session) -> PermissionCategoriesPublic:
    """权限分类列表"""
    rows = list_categories(session=session)
    return PermissionCategoriesPublic(
        count=len(rows),
        data=[
            PermissionCategoryPublic(
                id=row.id,
                name=row.name,
                description=row.description,
                sort_order=row.sort_order,
                is_active=row.is_active,
            )
            for row in rows
        ],
    )


def get_permissions(
    *, session: Session, action: ActionType | None = None
) -> PermissionsPublic:
    """权限列表（可按动作类型过滤）"""
    rows = list_permissions(session=session, action=action)
    items = [
        _to_permission_public(permission=permission, category=category)
        for permission, category in rows
    ]
    return PermissionsPublic(count=len(items), data=items)


def get_permission_tree(*, session: Session) -> PermissionTreePublic:
    """权限树：分类 → 权限，供角色授权界面使用"""
    categories = list_categories(session=session)
    rows = list_permissions(session=session)
    grouped: dict[uuid.UUID, list[PermissionPublic]] = {}
    for permission, category in rows:
        grouped.setdefault(category.id, []).append(
            _to_permission_public(permission=permission, category=category)
        )
    data = [
        PermissionTreeCategory(
            id=category.id,
            name=category.name,
            description=category.description,
            sort_order=category.sort_order,
            permissions=grouped.get(category.id, []),
        )
        for category in categories
    ]
    return PermissionTreePublic(count=len(data), data=data)


def get_active_permission_codes(*, session: Session) -> set[str]:
    """全部有效权限码，供超管的权限展示与权限检查使用"""
    return list_active_permission_codes(session=session)
