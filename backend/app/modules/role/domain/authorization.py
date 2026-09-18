"""角色模块：授权规则

本层只做纯规则判定，不依赖数据库、Web 框架与外部服务，
取数与缓存由 application / api 层负责提供输入。
"""


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
    - 其他用户：权限码必须来自角色授予的集合。
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
