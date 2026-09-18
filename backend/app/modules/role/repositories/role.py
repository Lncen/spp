"""角色模块：数据访问层

只负责数据查询与持久化，不编排业务流程。
"""

import uuid

from fastapi import HTTPException
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, delete, func, or_, select

from app.modules.permission.models import Permission, PermissionCategory
from app.modules.role.models import Role, RolePermission, UserRole


def create_role_row(
    *,
    session: Session,
    code: str,
    name: str,
    description: str | None,
    sort_order: int,
    is_system: bool,
    created_by: uuid.UUID | None,
) -> Role:
    """创建角色并加入会话（不提交，由调用方控制事务）"""
    role = Role(
        code=code,
        name=name,
        description=description,
        sort_order=sort_order,
        is_system=is_system,
        created_by=created_by,
    )
    session.add(role)
    session.flush()
    return role


def get_role(*, session: Session, role_id: uuid.UUID) -> Role | None:
    """按 ID 查询角色"""
    return session.get(Role, role_id)


def get_role_or_404(*, session: Session, role_id: uuid.UUID) -> Role:
    """按 ID 查询角色，不存在时抛出 404"""
    role = get_role(session=session, role_id=role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return role


def get_role_by_code(*, session: Session, code: str) -> Role | None:
    """按角色码查询角色"""
    return session.exec(select(Role).where(col(Role.code) == code)).first()


def delete_role_row(*, session: Session, role: Role) -> None:
    """删除角色及其角色权限、用户角色关联（不提交，由调用方控制事务）"""
    session.exec(
        delete(RolePermission).where(col(RolePermission.role_id) == role.id)
    )
    session.exec(delete(UserRole).where(col(UserRole.role_id) == role.id))
    session.delete(role)
    session.flush()


def _role_filters(keyword: str | None) -> list[ColumnElement[bool]]:
    """角色列表筛选条件"""
    if not keyword or not keyword.strip():
        return []
    pattern = f"%{keyword.strip()}%"
    return [or_(col(Role.code).ilike(pattern), col(Role.name).ilike(pattern))]


def list_roles(
    *, session: Session, skip: int, limit: int, keyword: str | None = None
) -> list[Role]:
    """角色列表，按排序值与角色码升序"""
    statement = (
        select(Role)
        .where(*_role_filters(keyword))
        .order_by(col(Role.sort_order), col(Role.code))
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def count_roles(*, session: Session, keyword: str | None = None) -> int:
    """角色总数（与列表同条件）"""
    statement = select(func.count()).select_from(Role).where(*_role_filters(keyword))
    return session.exec(statement).one()


def list_role_permission_codes(
    *, session: Session, role_id: uuid.UUID
) -> set[str]:
    """角色持有的有效权限码集合"""
    statement = (
        select(Permission.code)
        .select_from(RolePermission)
        .join(Permission, col(RolePermission.permission_id) == col(Permission.id))
        .join(
            PermissionCategory,
            col(Permission.category_id) == col(PermissionCategory.id),
        )
        .where(
            col(RolePermission.role_id) == role_id,
            col(Permission.is_active).is_(True),
            col(PermissionCategory.is_active).is_(True),
        )
    )
    return set(session.exec(statement).all())


def replace_role_permissions(
    *,
    session: Session,
    role_id: uuid.UUID,
    permission_ids: list[uuid.UUID],
    created_by: uuid.UUID | None,
) -> None:
    """全量覆盖角色权限（不提交，由调用方控制事务）"""
    session.exec(
        delete(RolePermission).where(col(RolePermission.role_id) == role_id)
    )
    session.flush()
    for permission_id in dict.fromkeys(permission_ids):
        session.add(
            RolePermission(
                role_id=role_id,
                permission_id=permission_id,
                created_by=created_by,
            )
        )
    session.flush()


def list_user_roles(*, session: Session, user_id: uuid.UUID) -> list[Role]:
    """用户已分配的角色列表"""
    statement = (
        select(Role)
        .join(UserRole, col(UserRole.role_id) == col(Role.id))
        .where(col(UserRole.user_id) == user_id)
        .order_by(col(Role.sort_order), col(Role.code))
    )
    return list(session.exec(statement).all())


def get_user_role(
    *, session: Session, user_id: uuid.UUID, role_id: uuid.UUID
) -> UserRole | None:
    """查询用户角色关联"""
    return session.exec(
        select(UserRole).where(
            col(UserRole.user_id) == user_id,
            col(UserRole.role_id) == role_id,
        )
    ).first()


def add_user_role(
    *,
    session: Session,
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    created_by: uuid.UUID | None,
) -> UserRole:
    """新增用户角色关联并加入会话（不提交）"""
    user_role = UserRole(
        user_id=user_id,
        role_id=role_id,
        created_by=created_by,
    )
    session.add(user_role)
    session.flush()
    return user_role


def delete_user_role(
    *, session: Session, user_id: uuid.UUID, role_id: uuid.UUID
) -> None:
    """删除用户角色关联（不提交）"""
    session.exec(
        delete(UserRole).where(
            col(UserRole.user_id) == user_id,
            col(UserRole.role_id) == role_id,
        )
    )
    session.flush()


def list_user_ids_by_role(
    *, session: Session, role_id: uuid.UUID
) -> list[uuid.UUID]:
    """查询持有该角色的全部用户 ID，用于缓存失效"""
    statement = select(UserRole.user_id).where(col(UserRole.role_id) == role_id)
    return list(session.exec(statement).all())


def get_user_permission_codes(
    *, session: Session, user_id: uuid.UUID
) -> set[str]:
    """用户经有效角色获得的全部有效权限码"""
    statement = (
        select(Permission.code)
        .select_from(UserRole)
        .join(Role, col(UserRole.role_id) == col(Role.id))
        .join(RolePermission, col(RolePermission.role_id) == col(Role.id))
        .join(Permission, col(RolePermission.permission_id) == col(Permission.id))
        .join(
            PermissionCategory,
            col(Permission.category_id) == col(PermissionCategory.id),
        )
        .where(
            col(UserRole.user_id) == user_id,
            col(Role.is_active).is_(True),
            col(RolePermission.is_active).is_(True),
            col(Permission.is_active).is_(True),
            col(PermissionCategory.is_active).is_(True),
        )
    )
    return set(session.exec(statement).all())
