"""权限动作类型

``permission.action`` 表示动作类型，只用于权限列表的分组展示与筛选。
权限分类、权限码与说明由初始化脚本 ``app/init_models_data/permissions.py``
的权限清单维护；代码中引用权限码统一走 ``require_permission``，导入期校验，
未登记直接启动失败。
"""

from enum import StrEnum


class ActionType(StrEnum):
    """权限动作类型"""

    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    MANAGE = "manage"
