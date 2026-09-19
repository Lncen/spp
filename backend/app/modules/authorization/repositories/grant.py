"""授权模块：数据访问层

只负责授权关系（角色权限、用户角色、用户直授权限）的查询与持久化，
不编排业务流程；写入函数均不提交事务，由调用方控制。
"""

import uuid

from sqlalchemy import or_
from sqlmodel import Session, col, delete, select

from app.modules.authorization.domain.authorization import GrantEffect
from app.modules.authorization.models import (
    RolePermission,
    UserPermission,
    UserRole,
)
from app.modules.permission.models import Permission, PermissionCategory
from app.modules.role.models import Role
from app.modules.user.models import User


# --------------------------------------------------------------------------- #
# 角色 → 权限
# --------------------------------------------------------------------------- #
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
) -> None:
    """全量覆盖角色权限（不提交，由调用方控制事务）"""
    session.exec(
        delete(RolePermission).where(col(RolePermission.role_id) == role_id)
    )
    session.flush()
    for permission_id in dict.fromkeys(permission_ids):
        session.add(RolePermission(role_id=role_id, permission_id=permission_id))
    session.flush()


# --------------------------------------------------------------------------- #
# 用户 → 角色
# --------------------------------------------------------------------------- #
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


# --------------------------------------------------------------------------- #
# 用户 → 权限（直授）
# --------------------------------------------------------------------------- #
def _list_user_permission_codes_by_effect(
    *, session: Session, user_id: uuid.UUID, effect: GrantEffect
) -> set[str]:
    """用户指定授权效果（allow / deny）下的有效权限码集合"""
    statement = (
        select(Permission.code)
        .select_from(UserPermission)
        .join(
            Permission, col(UserPermission.permission_id) == col(Permission.id)
        )
        .join(
            PermissionCategory,
            col(Permission.category_id) == col(PermissionCategory.id),
        )
        .where(
            col(UserPermission.user_id) == user_id,
            col(UserPermission.effect) == effect,
            col(Permission.is_active).is_(True),
            col(PermissionCategory.is_active).is_(True),
        )
    )
    return set(session.exec(statement).all())


def list_user_allowed_permission_codes(
    *, session: Session, user_id: uuid.UUID
) -> set[str]:
    """用户被直接授予（allow）的有效权限码集合"""
    return _list_user_permission_codes_by_effect(
        session=session, user_id=user_id, effect=GrantEffect.ALLOW
    )


def list_user_denied_permission_codes(
    *, session: Session, user_id: uuid.UUID
) -> set[str]:
    """用户被显式拒绝（deny）的有效权限码集合"""
    return _list_user_permission_codes_by_effect(
        session=session, user_id=user_id, effect=GrantEffect.DENY
    )


def _replace_user_permissions_by_effect(
    *,
    session: Session,
    user_id: uuid.UUID,
    permission_ids: list[uuid.UUID],
    effect: GrantEffect,
    created_by: uuid.UUID | None,
) -> None:
    """全量覆盖用户指定效果的直授权限（不提交，由调用方控制事务）

    同一权限不会同时存在两种效果：目标权限上已存在的另一种效果记录会被覆盖，
    即对该权限而言「最后显式写入的一方生效」。
    """
    session.exec(
        delete(UserPermission).where(
            col(UserPermission.user_id) == user_id,
            col(UserPermission.effect) == effect,
        )
    )
    session.flush()
    target_ids = list(dict.fromkeys(permission_ids))
    if target_ids:
        session.exec(
            delete(UserPermission).where(
                col(UserPermission.user_id) == user_id,
                col(UserPermission.permission_id).in_(target_ids),
            )
        )
        session.flush()
    for permission_id in target_ids:
        session.add(
            UserPermission(
                user_id=user_id,
                permission_id=permission_id,
                effect=effect,
                created_by=created_by,
            )
        )
    session.flush()


def replace_user_allowed_permissions(
    *,
    session: Session,
    user_id: uuid.UUID,
    permission_ids: list[uuid.UUID],
    created_by: uuid.UUID | None,
) -> None:
    """全量覆盖用户直授允许（不提交，由调用方控制事务）"""
    _replace_user_permissions_by_effect(
        session=session,
        user_id=user_id,
        permission_ids=permission_ids,
        effect=GrantEffect.ALLOW,
        created_by=created_by,
    )


def replace_user_denied_permissions(
    *,
    session: Session,
    user_id: uuid.UUID,
    permission_ids: list[uuid.UUID],
    created_by: uuid.UUID | None,
) -> None:
    """全量覆盖用户直授拒绝（不提交，由调用方控制事务）"""
    _replace_user_permissions_by_effect(
        session=session,
        user_id=user_id,
        permission_ids=permission_ids,
        effect=GrantEffect.DENY,
        created_by=created_by,
    )


def delete_user_permission(
    *, session: Session, user_id: uuid.UUID, permission_id: uuid.UUID
) -> None:
    """删除某权限上的用户直授记录（不区分允许 / 拒绝，不提交）"""
    session.exec(
        delete(UserPermission).where(
            col(UserPermission.user_id) == user_id,
            col(UserPermission.permission_id) == permission_id,
        )
    )
    session.flush()


# --------------------------------------------------------------------------- #
# 有效权限计算
# --------------------------------------------------------------------------- #
def list_user_role_permission_codes(
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


def list_user_effective_permission_codes(
    *, session: Session, user_id: uuid.UUID
) -> set[str]:
    """用户有效权限码：角色授予 ∪ 直授允许 − 直授拒绝"""
    return (
        list_user_role_permission_codes(session=session, user_id=user_id)
        | list_user_allowed_permission_codes(session=session, user_id=user_id)
    ) - list_user_denied_permission_codes(session=session, user_id=user_id)


def list_active_user_ids_by_permission_code(
    *, session: Session, code: str
) -> list[uuid.UUID]:
    """持有指定权限码的启用用户 ID（超管视为持有全部权限，deny 优先）"""
    role_granted = (
        select(UserRole.user_id)
        .join(Role, col(UserRole.role_id) == col(Role.id))
        .join(RolePermission, col(RolePermission.role_id) == col(Role.id))
        .join(
            Permission, col(RolePermission.permission_id) == col(Permission.id)
        )
        .join(
            PermissionCategory,
            col(Permission.category_id) == col(PermissionCategory.id),
        )
        .where(
            col(Role.is_active).is_(True),
            col(RolePermission.is_active).is_(True),
            col(Permission.code) == code,
            col(Permission.is_active).is_(True),
            col(PermissionCategory.is_active).is_(True),
        )
    )
    directly_allowed = (
        select(UserPermission.user_id)
        .join(
            Permission, col(UserPermission.permission_id) == col(Permission.id)
        )
        .join(
            PermissionCategory,
            col(Permission.category_id) == col(PermissionCategory.id),
        )
        .where(
            col(UserPermission.effect) == GrantEffect.ALLOW,
            col(Permission.code) == code,
            col(Permission.is_active).is_(True),
            col(PermissionCategory.is_active).is_(True),
        )
    )
    directly_denied = (
        select(UserPermission.user_id)
        .join(
            Permission, col(UserPermission.permission_id) == col(Permission.id)
        )
        .where(
            col(UserPermission.effect) == GrantEffect.DENY,
            col(Permission.code) == code,
        )
    )
    statement = select(User.id).where(
        col(User.is_active).is_(True),
        or_(
            col(User.is_superuser).is_(True),
            col(User.id).in_(role_granted),
            col(User.id).in_(directly_allowed),
        ),
        col(User.id).not_in(directly_denied),
    )
    return [user_id for user_id in session.exec(statement).all() if user_id]


# --------------------------------------------------------------------------- #
# 授权清理
# --------------------------------------------------------------------------- #
def delete_role_grants(
    *, session: Session, role_id: uuid.UUID
) -> list[uuid.UUID]:
    """删除角色的权限授权与用户角色分配，返回受影响用户 ID（不提交）

    由调用方在删除角色前调用，以便提交后失效这些用户的权限缓存。
    """
    affected_user_ids = list_user_ids_by_role(session=session, role_id=role_id)
    session.exec(
        delete(RolePermission).where(col(RolePermission.role_id) == role_id)
    )
    session.exec(delete(UserRole).where(col(UserRole.role_id) == role_id))
    session.flush()
    return affected_user_ids
