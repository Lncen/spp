"""全局设置模块：默认开关定义"""

from enum import StrEnum
from typing import Any


class SettingType(StrEnum):
    """设置类型：值对应模块名，便于识别设置归属"""

    SYSTEM = "system"  # 系统级设置
    AUTH = "auth"  # 认证模块
    AUTOMATION = "automation"  # 自动化模块
    IMAGE = "image"  # 图片模块
    ITEM = "item"  # 商品条目模块
    LEVEL = "level"  # 等级模块
    NOTIFICATION = "notification"  # 通知模块
    ORDER = "order"  # 订单模块
    PRICE_TEMPLATE = "price_template"  # 价格模板模块
    PRODUCT = "product"  # 产品模块
    SETTING = "setting"  # 设置模块自身
    SUPPLIER = "supplier"  # 供应商模块
    USER = "user"  # 用户模块
    WALLET = "wallet"  # 钱包模块
    OTHER = "other"  # 其他 / 兜底


# 自动化任务归档数据保留天数
AUTOMATION_TASK_RETENTION_DAYS = "automation_task_retention_days"

# 通知记录数据保留天数
NOTIFICATION_RETENTION_DAYS = "notification_retention_days"

# 已完成订单数据保留天数
ORDER_RETENTION_DAYS = "order_retention_days"

# 钱包流水数据保留天数
WALLET_TRANSACTION_RETENTION_DAYS = "wallet_transaction_retention_days"

# 每个键包含：value 默认值、description 说明
DEFAULT_SETTINGS: dict[str, dict[str, Any]] = {
    "maintenance_mode": {
        "value": False,
        "description": "开启后全站暂停服务",
        "type": SettingType.SYSTEM,
    },
    "order_enabled": {
        "value": True,
        "description": "是否允许用户下单",
        "type": SettingType.SYSTEM,
    },
    "login_fail_limit": {
        "value": 50,
        "description": "登录失败次数上限，达到后锁定该账号",
        "type": SettingType.AUTH,
    },
    "login_lockout_minutes": {
        "value": 15,
        "description": "登录失败锁定分钟数，到期后自动解锁",
        "type": SettingType.AUTH,
    },
    "allow_delete_account": {
        "value": False,
        "description": "允许用户自助删除自己的账号",
        "type": SettingType.USER,
    },
    AUTOMATION_TASK_RETENTION_DAYS: {
        "value": 3,
        "description": "自动化任务归档数据保留天数，到期后物理删除",
        "type": SettingType.AUTOMATION,
    },
    NOTIFICATION_RETENTION_DAYS: {
        "value": 30,
        "description": "通知记录数据保留天数，到期后物理删除",
        "type": SettingType.NOTIFICATION,
    },
    ORDER_RETENTION_DAYS: {
        "value": 7,
        "description": "已完成订单数据保留天数，到期后物理删除（保留钱包流水）",
        "type": SettingType.ORDER,
    },
    WALLET_TRANSACTION_RETENTION_DAYS: {
        "value": 7,
        "description": "钱包流水数据保留天数，到期后物理删除",
        "type": SettingType.WALLET,
    },
}


def get_default_setting(key: str) -> dict[str, Any] | None:
    """获取某个键的默认定义，不存在返回 None"""
    return DEFAULT_SETTINGS.get(key)
