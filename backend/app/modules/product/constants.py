"""商品模块：常量"""

from decimal import Decimal
from enum import IntEnum

COEFF_MIN = Decimal("0.01")
COEFF_MAX = Decimal("9.99")


class ProductType(IntEnum):
    """商品类型"""

    NORMAL_PRODUCT = 1  # 普通商品
    CARD = 2  # 实体卡券 / 储值卡
    GIFT_CARD = 3  # 礼品卡
    DIGITAL_CONTENT = 4  # 虚拟商品 / 数字内容
    SERVICE = 5  # 服务类商品
    COURSE = 6  # 课程
    GAME_ITEM = 7  # 游戏道具 / 游戏虚拟物品
    OTHER = 8  # 其他类型


class ProductStatus(IntEnum):
    """商品状态"""

    PENDING_REVIEW = 1  # 待审核 (1)
    REJECTED = 2  # 已驳回 (2)
    READY = 3  # 待上架 / 已就绪 (3)
    OFF_SHELF = 5  # 已下架 (5)
    WITHDRAWN = 6  # 已撤回 (6)
    APPROVED = 7  # 在售
    SOLD_OUT = 8  # 已售罄 (8)


class SyncStatus(IntEnum):
    """上游同步状态"""

    SUCCESS = 1  # 同步成功
    FAILED = 2  # 同步异常


class RedeemType(IntEnum):
    """发货方式"""

    AUTOMATIC = 1  # 自动发货
    MANUAL = 2  # 手动发货
    AUTO_API = 3  # API发货


class SourceType(IntEnum):
    """商品来源"""

    SUPPLIER = 1  # 供应商模式
    LOCAL = 2  # 本地/同城业务
    CROSS_BORDER = 3  # 跨境电商
    UGC = 4  # 用户生成内容 (C2C/二手)
    JOINT_OPERATION = 5  # 联营模式
    API_INTEGRATION = 6  # API系统直连
    MANUAL = 7  # 手动/人工操作
    DISTRIBUTOR = 8  # 分销商模式


class InputType(IntEnum):
    """下单参数输入类型"""

    TEXT = 1  # 单行文本输入框
    TEXTAREA = 2  # 多行文本输入框
    SELECT = 3  # 单选下拉框
    PASSWORD = 4  # 密码输入框
    MULTI_SELECT = 5  # 多选下拉框 / 多选控件
    NUMBER = 6  # 数字输入框
    MULTIPLY = 7  # 乘法运算 / 批量数值处理 (视具体业务而定)
    MULTIPLY_DROPDOWN = 8  # 乘法下拉框 / 批量选择下拉框
    SWITCH = 9  # 开关控件 (Switch / Toggle)
    QQ_NUMBER = 10  # QQ号输入框 (带格式校验)
    PHONE_NUMBER = 11  # 手机号输入框 (带格式校验)
    EMAIL = 12  # 邮箱输入框 (带格式校验)
    LINK_EXTRACT = 13  # 链接提取器 (自动从文本中抓取URL)
    ID_EXTRACT = 14  # ID提取器 (自动从文本中抓取特定ID)
    POST_ID = 15  # 帖子/文章ID输入框


class RuleType(IntEnum):
    """定价规则（由字段派生，不落库）"""

    FIXED_PRICE = 1
    PERCENTAGE_PRICE = 2
    CATEGORY_PRICE = 3
