"""订单模块：常量"""

from enum import IntEnum

from app.modules.product.constants import ProductStatus


class OrderStatus(IntEnum):
    """订单状态"""

    CREATED = 1
    PROCESSING = 2
    COMPLETED = 3
    CANCELED = 4
    REFUNDED = 5
    FAILED = 6


# 可下单的商品状态
SALABLE_PRODUCT_STATUSES = frozenset(
    {ProductStatus.READY, ProductStatus.APPROVED}
)
