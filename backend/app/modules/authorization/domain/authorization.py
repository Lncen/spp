"""授权模块：授权类型与授权规则

本层只做纯类型与规则判定，不依赖数据库、Web 框架与外部服务，
取数与缓存由 application / api 层负责提供输入。
"""

from enum import StrEnum


class GrantEffect(StrEnum):
    """授权效果

    ``allow``：直接授予；``deny``：显式拒绝。
    有效权限 = 角色授予 ∪ 直授允许 − 直授拒绝。
    同一权限不会同时存在两种效果：最后显式写入的一方生效（见 repositories）。
    """

    ALLOW = "allow"
    DENY = "deny"


def is_permission_granted(
    *,
    code: str,
    is_active: bool,
    is_superuser: bool,
    permission_codes: set[str],
) -> bool:
    """判断用户是否持有某个权限码

    - 账号停用：一律拒绝；
    - 超级管理员：系统级 bypass；
    - 其他用户：权限码必须来自角色授予与用户直授的并集。
    """
    if not is_active:
        return False
    if is_superuser:
        return True
    return code in permission_codes


def can_grant_permission_codes(
    *,
    operator_is_superuser: bool,
    operator_codes: set[str],
    target_codes: set[str],
) -> bool:
    """防提权规则：非超管只能授予自己已持有的权限码"""
    if operator_is_superuser:
        return True
    return target_codes <= operator_codes
