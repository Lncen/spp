"""权限定义模块：数据访问层（只读）

权限定义仅由初始化脚本写入，仓库层只提供查询能力。
权限码直接存储在 ``permission.code``，分类只用于分组展示。
"""

import uuid

from sqlmodel import Session, col, select

from app.modules.permission.domain.catalog import ActionType
from app.modules.permission.models import Permission, PermissionCategory


def list_categories(
    *, session: Session, include_inactive: bool = False
) -> list[PermissionCategory]:
    """权限分类列表，按排序值升序"""
    statement = select(PermissionCategory).order_by(
        col(PermissionCategory.sort_order), col(PermissionCategory.name)
    )
    if not include_inactive:
        statement = statement.where(col(PermissionCategory.is_active).is_(True))
    return list(session.exec(statement).all())


def list_permissions(
    *,
    session: Session,
    action: ActionType | None = None,
    include_inactive: bool = False,
) -> list[tuple[Permission, PermissionCategory]]:
    """权限列表，返回 (权限, 所属分类) 元组，按分类与权限排序"""
    statement = (
        select(Permission, PermissionCategory)
        .join(
            PermissionCategory,
            col(Permission.category_id) == col(PermissionCategory.id),
        )
        .order_by(
            col(PermissionCategory.sort_order),
            col(Permission.sort_order),
            col(Permission.code),
        )
    )
    if not include_inactive:
        statement = statement.where(
            col(Permission.is_active).is_(True),
            col(PermissionCategory.is_active).is_(True),
        )
    if action is not None:
        statement = statement.where(col(Permission.action) == action)
    return [
        (permission, category)
        for permission, category in session.exec(statement).all()
    ]


def list_permissions_by_ids(
    *, session: Session, permission_ids: list[uuid.UUID]
) -> list[tuple[Permission, PermissionCategory]]:
    """按 ID 批量查询有效权限，返回 (权限, 所属分类) 元组"""
    if not permission_ids:
        return []
    statement = (
        select(Permission, PermissionCategory)
        .join(
            PermissionCategory,
            col(Permission.category_id) == col(PermissionCategory.id),
        )
        .where(
            col(Permission.id).in_(permission_ids),
            col(Permission.is_active).is_(True),
            col(PermissionCategory.is_active).is_(True),
        )
    )
    return [
        (permission, category)
        for permission, category in session.exec(statement).all()
    ]


def get_permission_by_code(
    *, session: Session, code: str
) -> Permission | None:
    """按权限码查询权限"""
    return session.exec(select(Permission).where(col(Permission.code) == code)).first()


def list_active_permission_codes(*, session: Session) -> set[str]:
    """全部有效权限码集合，用于超管权限展示与自检"""
    statement = (
        select(Permission.code)
        .select_from(Permission)
        .join(
            PermissionCategory,
            col(Permission.category_id) == col(PermissionCategory.id),
        )
        .where(
            col(Permission.is_active).is_(True),
            col(PermissionCategory.is_active).is_(True),
        )
    )
    return set(session.exec(statement).all())


def list_all_permission_codes(*, session: Session) -> set[str]:
    """全部权限码集合（含已停用），用于初始化脚本对账"""
    return set(session.exec(select(Permission.code)).all())
