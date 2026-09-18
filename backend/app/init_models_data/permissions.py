"""权限定义初始数据：权限分类与权限项清单

- 权限清单以列表形式声明在本文件，是权限定义的唯一来源；
- 分类按 ``name`` 匹配，权限项按 ``code`` 匹配，已存在则更新字段，不存在则新增；
- 清单中已移除的分类/权限置 ``is_active=False``，不物理删除（保留历史授权关系）；
- 同步完成后整体失效权限缓存，因为权限定义影响所有用户的判定结果。
"""

from typing import TypedDict

from sqlmodel import Session, col, select

from app.modules.permission.domain.catalog import ActionType
from app.modules.permission.models import Permission, PermissionCategory
from app.modules.role.infrastructure.cache import invalidate_all_permissions


class PermissionData(TypedDict):
    """清单中的单个权限项"""

    code: str
    action: ActionType
    name: str
    description: str


class PermissionCategoryData(TypedDict):
    """清单中的单个权限分类"""

    name: str
    description: str
    sort_order: int
    permissions: list[PermissionData]


# 权限清单：新增权限只需在对应分类的 permissions 里追加一项，列表顺序即 sort_order
PERMISSION_CATEGORIES_DATA: list[PermissionCategoryData] = [
    {
        "name": "角色管理",
        "description": "角色、角色权限与用户角色分配",
        "sort_order": 1,
        "permissions": [
            {
                "code": "role:view",
                "action": ActionType.VIEW,
                "name": "查看角色",
                "description": "查看角色列表、角色详情与用户已分配角色",
            },
            {
                "code": "role:create",
                "action": ActionType.CREATE,
                "name": "创建角色",
                "description": "创建自定义角色",
            },
            {
                "code": "role:update",
                "action": ActionType.UPDATE,
                "name": "修改角色",
                "description": "修改角色名称、描述与启停状态",
            },
            {
                "code": "role:delete",
                "action": ActionType.MANAGE,
                "name": "删除角色",
                "description": "删除自定义角色，并解除该角色下的用户分配",
            },
            {
                "code": "role:assign_user",
                "action": ActionType.MANAGE,
                "name": "分配用户角色",
                "description": "为用户分配或移除角色",
            },
            {
                "code": "role:assign_permission",
                "action": ActionType.MANAGE,
                "name": "分配角色权限",
                "description": "调整角色持有的权限集合",
            },
        ],
    },
    {
        "name": "权限管理",
        "description": "权限分类与权限项查看",
        "sort_order": 2,
        "permissions": [
            {
                "code": "permission:view",
                "action": ActionType.VIEW,
                "name": "查看分类",
                "description": "查看权限分类、权限列表与权限树",
            },
        ],
    },
]

# 清单中登记的全部权限码，供 require_permission 导入期校验使用
ALL_PERMISSION_CODES: frozenset[str] = frozenset(
    item["code"]
    for category in PERMISSION_CATEGORIES_DATA
    for item in category["permissions"]
)


def is_registered_permission(code: str) -> bool:
    """判断权限码是否已在权限清单中登记"""
    return code in ALL_PERMISSION_CODES


def seed_permission_catalog(*, session: Session) -> None:
    """播种权限分类与权限项，幂等安全（已存在则更新，不存在则新增）"""
    # 1. 遍历每一个分类
    for category_data in PERMISSION_CATEGORIES_DATA:
        category = session.exec(
            select(PermissionCategory).where(
                col(PermissionCategory.name) == category_data["name"]
            )
        ).first()

        # 2. 分类不存在则新增，已存在则更新展示字段
        if category is None:
            category = PermissionCategory(
                name=category_data["name"],
                description=category_data["description"],
                sort_order=category_data["sort_order"],
            )
            session.add(category)
            # 新建分类要先 flush 拿到 id，权限项才能关联
            session.flush()
        else:
            category.description = category_data["description"]
            category.sort_order = category_data["sort_order"]
            category.is_active = True

        # 3. 遍历该分类下的权限项，按 code 查重，列表顺序即 sort_order
        for index, item in enumerate(category_data["permissions"], start=1):
            permission = session.exec(
                select(Permission).where(col(Permission.code) == item["code"])
            ).first()

            if permission is None:
                session.add(
                    Permission(
                        code=item["code"],
                        category_id=category.id,
                        action=item["action"],
                        name=item["name"],
                        description=item["description"],
                        sort_order=index,
                    )
                )
                continue

            permission.category_id = category.id
            permission.action = item["action"]
            permission.name = item["name"]
            permission.description = item["description"]
            permission.sort_order = index
            permission.is_active = True

    # 4. 清单中已移除的分类与权限只停用，不物理删除，避免历史授权关系断裂
    for permission in session.exec(select(Permission)).all():
        if permission.code not in ALL_PERMISSION_CODES and permission.is_active:
            permission.is_active = False

    category_names = {
        category_data["name"] for category_data in PERMISSION_CATEGORIES_DATA
    }
    for category in session.exec(select(PermissionCategory)).all():
        if category.name not in category_names and category.is_active:
            category.is_active = False

    # 5. 统一提交事务；权限定义影响所有用户的判定结果，提交后整体失效缓存
    session.commit()
    invalidate_all_permissions()
