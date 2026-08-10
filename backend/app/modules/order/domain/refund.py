"""订单模块：退款领域规则"""

from decimal import Decimal

from app.modules.order.models import Order


def calc_refund_amount(*, db_order: Order) -> Decimal:
    """退单退款金额 = (订单数量 - (当前数量 - 开始数量)) × 成交单价，限制在 [0, 订单金额]"""
    unfinished = db_order.quantity - (
        db_order.current_quantity - db_order.start_quantity
    )
    amount = Decimal(max(unfinished, 0)) * db_order.unit_price
    return min(amount, db_order.total_amount)
