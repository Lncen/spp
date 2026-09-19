"""系统内置角色初始数据：把内置角色清单同步到角色表

- 角色清单以列表形式声明在本文件，只维护 ``is_system=True`` 的角色，自定义角色不受影响；
- 角色按 ``code`` 匹配，已存在则更新字段，不存在则新增；
- 权限码取自 ``app/init_models_data/permissions.py`` 的权限清单；
- 同步完成后整体失效权限缓存，因为内置角色的授权变化会影响其下所有用户。
"""

import uuid
from typing import TypedDict

from sqlmodel import Session, col, delete, select

from app.init_models_data.permissions import ALL_PERMISSION_CODES
from app.modules.authorization.infrastructure.cache import invalidate_all_permissions
from app.modules.authorization.models import RolePermission
from app.modules.permission.models import Permission, PermissionCategory
from app.modules.role.models import Role


class SystemRoleData(TypedDict):
    """清单中的单个系统内置角色"""

    code: str
    name: str
    description: str
    sort_order: int
    permission_codes: list[str]


# 内置角色清单：admin 取权限清单内全部权限，新增权限自动纳入
SYSTEM_ROLES_DATA: list[SystemRoleData] = [
    {
        "code": "admin",
        "name": "系统管理员",
        "description": "拥有全部权限（超级管理员账号仍为系统级 bypass）",
        "sort_order": 1,
        "permission_codes": sorted(ALL_PERMISSION_CODES),
    },
]


def _permission_id_map(*, session: Session) -> dict[str, uuid.UUID]:
    """有效权限码 → 权限 ID 映射，供角色授权使用"""
    statement = (
        select(Permission.code, Permission.id)
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
    return dict(session.exec(statement).all())


def seed_system_roles(*, session: Session) -> None:
    """播种系统内置角色及其权限集合，幂等安全（已存在则更新，不存在则新增）"""
    # 1. 先取有效权限码 → 权限 ID 映射，后面按权限码授权
    permission_ids = _permission_id_map(session=session)

    # 2. 遍历每一个内置角色
    for role_data in SYSTEM_ROLES_DATA:
        role = session.exec(
            select(Role).where(col(Role.code) == role_data["code"])
        ).first()

        # 3. 角色不存在则新增，已存在则更新字段并重新启用
        if role is None:
            role = Role(
                code=role_data["code"],
                name=role_data["name"],
                description=role_data["description"],
                sort_order=role_data["sort_order"],
                is_system=True,
            )
            session.add(role)
            # 新建角色要先 flush 拿到 id，角色权限关联才能写入
            session.flush()
        else:
            role.name = role_data["name"]
            role.description = role_data["description"]
            role.sort_order = role_data["sort_order"]
            role.is_system = True
            role.is_active = True

        # 4. 同步角色权限集合：与清单不一致时整体重建
        wanted_ids = {
            permission_ids[code]
            for code in role_data["permission_codes"]
            if code in permission_ids
        }
        current_ids = set(
            session.exec(
                select(RolePermission.permission_id).where(
                    col(RolePermission.role_id) == role.id
                )
            ).all()
        )
        if current_ids == wanted_ids:
            continue
        session.exec(
            delete(RolePermission).where(col(RolePermission.role_id) == role.id)
        )
        session.flush()
        for permission_id in sorted(wanted_ids, key=str):
            session.add(RolePermission(role_id=role.id, permission_id=permission_id))

    # 5. 统一提交事务；内置角色的授权变化会影响其下所有用户，提交后整体失效缓存
    session.commit()
    invalidate_all_permissions()
