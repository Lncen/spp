"""价格模板模块：常量"""

from decimal import Decimal

# 默认折扣率：15 折，即基准价的 1.5 倍
DEFAULT_DISCOUNT_RATE = Decimal("1.5000")

LEVEL_MIN = 1
LEVEL_MAX = 10

MONEY_PRECISION = Decimal("0.01")
