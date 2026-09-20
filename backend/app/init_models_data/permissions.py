"""权限定义初始数据：权限分类与权限项清单

- 权限清单以列表形式声明在本文件，是权限定义的唯一来源；
- 分类按 ``name`` 匹配，权限项按 ``code`` 匹配，已存在则更新字段，不存在则新增；
- 清单中已移除的分类/权限置 ``is_active=False``，不物理删除（保留历史授权关系）；
- 同步完成后整体失效权限缓存，因为权限定义影响所有用户的判定结果。
"""

from typing import TypedDict

from sqlmodel import Session, col, select

from app.modules.authorization.infrastructure.cache import invalidate_all_permissions
from app.modules.permission.domain.catalog import ActionType
from app.modules.permission.models import Permission, PermissionCategory


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
    {
        "name": "用户管理",
        "description": "用户账号与密码找回邮件",
        "sort_order": 3,
        "permissions": [
            {
                "code": "user:view",
                "action": ActionType.VIEW,
                "name": "查看用户",
                "description": "查看用户列表、用户详情与密码找回邮件内容",
            },
            {
                "code": "user:create",
                "action": ActionType.CREATE,
                "name": "创建用户",
                "description": "创建新用户账号",
            },
            {
                "code": "user:update",
                "action": ActionType.UPDATE,
                "name": "修改用户",
                "description": "修改用户资料、等级、状态与余额字段",
            },
            {
                "code": "user:delete",
                "action": ActionType.MANAGE,
                "name": "删除用户",
                "description": "删除用户账号",
            },
            {
                "code": "user:assign_permission",
                "action": ActionType.MANAGE,
                "name": "分配用户权限",
                "description": "直接为用户授予或撤销权限（不含角色授予）",
            },
        ],
    },
    {
        "name": "等级管理",
        "description": "用户等级定义与折扣配置",
        "sort_order": 4,
        "permissions": [
            {
                "code": "level:view",
                "action": ActionType.VIEW,
                "name": "查看等级",
                "description": "查看用户等级列表与等级详情",
            },
            {
                "code": "level:update",
                "action": ActionType.UPDATE,
                "name": "修改等级",
                "description": "修改等级名称、描述与默认等级标记",
            },
        ],
    },
    {
        "name": "商品管理",
        "description": "商品与商品分类",
        "sort_order": 5,
        "permissions": [
            {
                "code": "product:view",
                "action": ActionType.VIEW,
                "name": "查看商品",
                "description": "查看商品列表与商品详情",
            },
            {
                "code": "product:create",
                "action": ActionType.CREATE,
                "name": "创建商品",
                "description": "创建商品及其关联配置",
            },
            {
                "code": "product:update",
                "action": ActionType.UPDATE,
                "name": "修改商品",
                "description": "修改商品及其关联配置",
            },
            {
                "code": "product:delete",
                "action": ActionType.MANAGE,
                "name": "删除商品",
                "description": "删除商品及其关联配置",
            },
            {
                "code": "product_category:view",
                "action": ActionType.VIEW,
                "name": "查看商品分类",
                "description": "查看商品分类列表、分类树与分类详情",
            },
            {
                "code": "product_category:create",
                "action": ActionType.CREATE,
                "name": "创建商品分类",
                "description": "创建商品分类",
            },
            {
                "code": "product_category:update",
                "action": ActionType.UPDATE,
                "name": "修改商品分类",
                "description": "修改商品分类名称、图标、排序与启停状态",
            },
            {
                "code": "product_category:delete",
                "action": ActionType.MANAGE,
                "name": "删除商品分类",
                "description": "删除商品分类（有子分类或商品时拒绝）",
            },
        ],
    },
    {
        "name": "订单管理",
        "description": "订单查询、代下单与售后操作",
        "sort_order": 6,
        "permissions": [
            {
                "code": "order:view",
                "action": ActionType.VIEW,
                "name": "查看订单",
                "description": "查看全部订单列表与订单详情",
            },
            {
                "code": "order:create",
                "action": ActionType.CREATE,
                "name": "代客下单",
                "description": "管理员代客下单与下单结算预览",
            },
            {
                "code": "order:update",
                "action": ActionType.UPDATE,
                "name": "修改订单",
                "description": "设置订单状态、补录供应商订单号与同步上游状态",
            },
            {
                "code": "order:cancel",
                "action": ActionType.MANAGE,
                "name": "取消订单",
                "description": "管理员取消待处理订单",
            },
            {
                "code": "order:fulfill",
                "action": ActionType.MANAGE,
                "name": "履约订单",
                "description": "手动履约订单",
            },
            {
                "code": "order:refund",
                "action": ActionType.MANAGE,
                "name": "订单退款",
                "description": "管理员手动退款并按指定金额入账",
            },
        ],
    },
    {
        "name": "钱包管理",
        "description": "用户钱包查询、启停与调账",
        "sort_order": 7,
        "permissions": [
            {
                "code": "wallet:view",
                "action": ActionType.VIEW,
                "name": "查看钱包",
                "description": "查看钱包列表、指定用户钱包与钱包流水",
            },
            {
                "code": "wallet:update",
                "action": ActionType.UPDATE,
                "name": "修改钱包状态",
                "description": "启用或停用钱包",
            },
            {
                "code": "wallet:adjust",
                "action": ActionType.MANAGE,
                "name": "钱包调账",
                "description": "管理员调账：正数入账、负数扣款",
            },
        ],
    },
    {
        "name": "供应商管理",
        "description": "供应商配置、上游商品与余额",
        "sort_order": 8,
        "permissions": [
            {
                "code": "supplier:view",
                "action": ActionType.VIEW,
                "name": "查看供应商",
                "description": "查看供应商列表与详情、平台选项、上游分类/商品与实时余额",
            },
            {
                "code": "supplier:create",
                "action": ActionType.CREATE,
                "name": "创建供应商",
                "description": "创建供应商",
            },
            {
                "code": "supplier:update",
                "action": ActionType.UPDATE,
                "name": "修改供应商",
                "description": "修改供应商信息（不含余额）",
            },
            {
                "code": "supplier:delete",
                "action": ActionType.MANAGE,
                "name": "删除供应商",
                "description": "删除供应商",
            },
            {
                "code": "supplier:sync",
                "action": ActionType.MANAGE,
                "name": "同步上游商品",
                "description": "创建上游商品同步任务并查询同步状态",
            },
        ],
    },
    {
        "name": "价格模板",
        "description": "等级折扣价格模板",
        "sort_order": 9,
        "permissions": [
            {
                "code": "price_template:view",
                "action": ActionType.VIEW,
                "name": "查看价格模板",
                "description": "查看价格模板列表与详情",
            },
            {
                "code": "price_template:create",
                "action": ActionType.CREATE,
                "name": "创建价格模板",
                "description": "创建价格模板",
            },
            {
                "code": "price_template:update",
                "action": ActionType.UPDATE,
                "name": "修改价格模板",
                "description": "修改价格模板与等级折扣",
            },
            {
                "code": "price_template:delete",
                "action": ActionType.MANAGE,
                "name": "删除价格模板",
                "description": "删除价格模板并级联删除规则",
            },
        ],
    },
    {
        "name": "通知",
        "description": "管理端通知记录与手动发送",
        "sort_order": 10,
        "permissions": [
            {
                "code": "notification:view",
                "action": ActionType.VIEW,
                "name": "查看通知",
                "description": "查看全部通知与投递记录",
            },
            {
                "code": "notification:create",
                "action": ActionType.CREATE,
                "name": "发送通知",
                "description": "手动发送通知（指定用户或群发）",
            },
            {
                "code": "notification:delete",
                "action": ActionType.MANAGE,
                "name": "删除通知",
                "description": "管理端删除通知记录及其投递记录",
            },
            {
                "code": "notification:retry",
                "action": ActionType.MANAGE,
                "name": "重试投递",
                "description": "重试失败的通知投递记录",
            },
        ],
    },
    {
        "name": "聊天",
        "description": "用户自助聊天能力与客服坐席接待",
        "sort_order": 11,
        "permissions": [
            {
                "code": "chat:self_view",
                "action": ActionType.VIEW,
                "name": "查看自己的聊天",
                "description": "查看聊天列表、聊天详情、消息与未读数，标记已读",
            },
            {
                "code": "chat:send",
                "action": ActionType.REPLY,
                "name": "发送聊天消息",
                "description": "在自己参与的聊天中通过实时通道发送消息",
            },
            {
                "code": "chat:create",
                "action": ActionType.CREATE,
                "name": "发起私聊",
                "description": "创建或复用与其他用户的私聊",
            },
            {
                "code": "chat:group:create",
                "action": ActionType.CREATE,
                "name": "创建群聊",
                "description": "创建群聊；群成员管理由群主身份或聊天成员管理权限决定",
            },
            {
                "code": "chat:participant:manage",
                "action": ActionType.MANAGE,
                "name": "管理聊天成员",
                "description": "管理任意聊天的成员（群主天然可管理自己的群）",
            },
        ],
    },
    {
        "name": "自动化",
        "description": "自动化规则、任务池与业务事件",
        "sort_order": 12,
        "permissions": [
            {
                "code": "automation_rule:view",
                "action": ActionType.VIEW,
                "name": "查看自动化规则",
                "description": "查看自动化规则列表与详情",
            },
            {
                "code": "automation_rule:create",
                "action": ActionType.CREATE,
                "name": "创建自动化规则",
                "description": "创建自动化规则",
            },
            {
                "code": "automation_rule:update",
                "action": ActionType.UPDATE,
                "name": "修改自动化规则",
                "description": "修改自动化规则与启停状态",
            },
            {
                "code": "automation_rule:delete",
                "action": ActionType.MANAGE,
                "name": "删除自动化规则",
                "description": "删除自动化规则",
            },
            {
                "code": "automation_task:view",
                "action": ActionType.VIEW,
                "name": "查看自动化任务",
                "description": "查看任务池、任务归档、任务详情与执行器选项",
            },
            {
                "code": "automation_task:create",
                "action": ActionType.CREATE,
                "name": "创建自动化任务",
                "description": "创建自动化任务",
            },
            {
                "code": "automation_task:manage",
                "action": ActionType.MANAGE,
                "name": "管理自动化任务",
                "description": "取消待执行任务与重试失败任务",
            },
            {
                "code": "automation_event:view",
                "action": ActionType.VIEW,
                "name": "查看自动化事件",
                "description": "查看自动化事件列表",
            },
            {
                "code": "automation_event:publish",
                "action": ActionType.CREATE,
                "name": "发布业务事件",
                "description": "手动发布业务事件并触发规则分发",
            },
        ],
    },
    {
        "name": "计划任务",
        "description": "Celery Beat 计划任务配置与执行",
        "sort_order": 13,
        "permissions": [
            {
                "code": "schedule:view",
                "action": ActionType.VIEW,
                "name": "查看计划任务",
                "description": "查看计划任务列表、详情、任务选项与执行状态",
            },
            {
                "code": "schedule:update",
                "action": ActionType.UPDATE,
                "name": "修改计划任务",
                "description": "修改计划任务配置",
            },
            {
                "code": "schedule:manage",
                "action": ActionType.MANAGE,
                "name": "执行与启停计划任务",
                "description": "立即执行一次计划任务，或启用、停用计划任务",
            },
        ],
    },
    {
        "name": "系统日志",
        "description": "系统日志与操作审计查询",
        "sort_order": 14,
        "permissions": [
            {
                "code": "system_log:view",
                "action": ActionType.VIEW,
                "name": "查看系统日志",
                "description": "查询系统日志列表与详情",
            },
            {
                "code": "audit_log:view",
                "action": ActionType.VIEW,
                "name": "查看操作审计",
                "description": "查询操作审计列表与详情",
            },
        ],
    },
    {
        "name": "数据备份",
        "description": "数据备份的创建、下载、恢复与删除",
        "sort_order": 15,
        "permissions": [
            {
                "code": "backup:view",
                "action": ActionType.VIEW,
                "name": "查看备份",
                "description": "查看备份列表与下载备份文件",
            },
            {
                "code": "backup:create",
                "action": ActionType.CREATE,
                "name": "创建备份",
                "description": "手动创建数据备份",
            },
            {
                "code": "backup:delete",
                "action": ActionType.MANAGE,
                "name": "删除备份",
                "description": "删除备份文件",
            },
            {
                "code": "backup:restore",
                "action": ActionType.MANAGE,
                "name": "恢复备份",
                "description": "从指定备份执行合并恢复",
            },
        ],
    },
    {
        "name": "图片管理",
        "description": "图片库与图片分类",
        "sort_order": 16,
        "permissions": [
            {
                "code": "image:view",
                "action": ActionType.VIEW,
                "name": "查看全部图片",
                "description": "查看全部用户上传的图片；不持有时仅可见本人上传与系统默认图片",
            },
            {
                "code": "image:upload",
                "action": ActionType.CREATE,
                "name": "上传图片",
                "description": "上传图片到图片库",
            },
            {
                "code": "image:update",
                "action": ActionType.UPDATE,
                "name": "修改图片",
                "description": "修改任意图片的分类；不持有时仅能修改本人上传的图片",
            },
            {
                "code": "image:delete",
                "action": ActionType.MANAGE,
                "name": "删除图片",
                "description": "删除任意图片；不持有时仅能删除本人上传的图片",
            },
            {
                "code": "image_category:view",
                "action": ActionType.VIEW,
                "name": "查看图片分类",
                "description": "查看图片分类列表、分类选项与分类详情",
            },
            {
                "code": "image_category:create",
                "action": ActionType.CREATE,
                "name": "创建图片分类",
                "description": "创建图片分类",
            },
            {
                "code": "image_category:update",
                "action": ActionType.UPDATE,
                "name": "修改图片分类",
                "description": "修改图片分类名称、说明、排序与启停状态",
            },
            {
                "code": "image_category:delete",
                "action": ActionType.MANAGE,
                "name": "删除图片分类",
                "description": "删除图片分类（有图片引用时拒绝）",
            },
        ],
    },
    {
        "name": "系统设置",
        "description": "全局开关与默认设置项",
        "sort_order": 17,
        "permissions": [
            {
                "code": "setting:update",
                "action": ActionType.UPDATE,
                "name": "修改系统设置",
                "description": "新增或更新全局设置项",
            },
        ],
    },
    {
        "name": "系统工具",
        "description": "系统自检与运维工具",
        "sort_order": 18,
        "permissions": [
            {
                "code": "system:test_email",
                "action": ActionType.MANAGE,
                "name": "发送测试邮件",
                "description": "发送测试邮件验证邮件配置",
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
