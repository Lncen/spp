"""供应商模块：领域常量"""

from enum import StrEnum


class PlatformEnum(StrEnum):
    """供应商平台枚举"""

    SELF = "self"  # 自营
    YLSUP = "ylsup"
