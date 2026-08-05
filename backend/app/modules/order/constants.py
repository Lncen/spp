"""订单模块：常量"""

from enum import IntEnum

from app.modules.product.constants import ProductStatus


class OrderStatus(IntEnum):
    """订单状态（与上游一致）"""

    PAID = 1  # 已付款
    PENDING = 2  # 待处理
    PROCESSING = 3  # 处理中
    SUPPLEMENTING = 4  # 补单中
    REFUNDING = 5  # 退单中
    COMPLETED = 6  # 已完成
    CANCELED = 7  # 已退单
    REFUNDED = 8  # 已退款
    EXCEPTION = 9  # 有异常
    APPLYING_AFTER_SALE = 10  # 申请售后中


# 可下单的商品状态
SALABLE_PRODUCT_STATUSES = frozenset({ProductStatus.APPROVED})
