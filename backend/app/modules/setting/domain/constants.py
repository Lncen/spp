"""全局设置模块：默认开关定义"""

from typing import Any

# 自动化任务归档数据保留天数
AUTOMATION_TASK_RETENTION_DAYS = "automation_task_retention_days"

# 每个键包含：value 默认值、description 说明
DEFAULT_SETTINGS: dict[str, dict[str, Any]] = {
    "maintenance_mode": {
        "value": False,
        "description": "开启后全站暂停服务",
    },
    "order_enabled": {
        "value": True,
        "description": "是否允许用户下单",
    },
    "login_fail_limit": {
        "value": 50,
        "description": "登录失败次数上限，达到后锁定该账号",
    },
    "login_lockout_minutes": {
        "value": 15,
        "description": "登录失败锁定分钟数，到期后自动解锁",
    },
    "allow_delete_account": {
        "value": False,
        "description": "是否允许用户自助删除账号，默认关闭",
    },
    AUTOMATION_TASK_RETENTION_DAYS: {
        "value": 3,
        "description": "自动化任务归档数据保留天数，到期后物理删除",
    },
}


def get_default_setting(key: str) -> dict[str, Any] | None:
    """获取某个键的默认定义，不存在返回 None"""
    return DEFAULT_SETTINGS.get(key)
