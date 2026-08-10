"""用户模块：领域常量与默认规则"""

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def default_username(email: str) -> str:
    """用户名未填写时默认使用邮箱"""
    return email
