"""订单模块：计价领域规则"""

import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlmodel import Session

from app.modules.price_template.constants import MONEY_PRECISION
from app.modules.price_template.service import get_user_price
from app.modules.product.product.models import ProductPricing


def money(value: Decimal) -> Decimal:
    """金额按业务精度四舍五入"""
    return value.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)


def calc_unit_price(
    *, session: Session, pricing: ProductPricing, user_level_id: uuid.UUID | None
) -> Decimal:
    """按定价规则计算成交单价"""
    base_price = pricing.cost_price + pricing.loss_price
    if pricing.fixed_price is not None:
        unit_price = pricing.fixed_price
    elif pricing.item_coefficient is not None:
        unit_price = base_price * pricing.item_coefficient
    else:
        unit_price = get_user_price(
            session=session,
            base_price=base_price,
            price_template_id=pricing.price_template_id,
            user_level_id=user_level_id,
        )
    return money(unit_price)
