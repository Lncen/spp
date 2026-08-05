"""商品模块：常量"""

from decimal import Decimal
from enum import IntEnum

COEFF_MIN = Decimal("0.01")
COEFF_MAX = Decimal("9.99")


class ProductType(IntEnum):
    """商品类型"""

    NORMAL_PRODUCT = 1
    CARD = 2
    GIFT_CARD = 3
    DIGITAL_CONTENT = 4
    SERVICE = 5
    COURSE = 6
    GAME_ITEM = 7
    OTHER = 8


class ProductStatus(IntEnum):
    """商品状态"""

    PENDING_REVIEW = 1
    REJECTED = 2
    READY = 3
    OFF_SHELF = 5
    WITHDRAWN = 6
    APPROVED = 7
    SOLD_OUT = 8


class RedeemType(IntEnum):
    """发货方式"""

    AUTOMATIC = 1
    MANUAL = 2
    AUTO_API = 3


class SourceType(IntEnum):
    """商品来源"""

    SUPPLIER = 1
    LOCAL = 2
    CROSS_BORDER = 3
    UGC = 4
    JOINT_OPERATION = 5
    API_INTEGRATION = 6
    MANUAL = 7
    DISTRIBUTOR = 8


class InputType(IntEnum):
    """下单参数输入类型"""

    TEXT = 1
    TEXTAREA = 2
    SELECT = 3
    PASSWORD = 4
    MULTI_SELECT = 5
    NUMBER = 6
    MULTIPLY = 7
    MULTIPLY_DROPDOWN = 8
    SWITCH = 9
    QQ_NUMBER = 10
    PHONE_NUMBER = 11
    EMAIL = 12
    LINK_EXTRACT = 13
    ID_EXTRACT = 14
    POST_ID = 15


class RuleType(IntEnum):
    """定价规则（由字段派生，不落库）"""

    FIXED_PRICE = 1
    PERCENTAGE_PRICE = 2
    CATEGORY_PRICE = 3
