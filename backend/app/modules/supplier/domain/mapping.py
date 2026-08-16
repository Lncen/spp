"""供应商模块：上游数据到本地业务字段的映射规则（纯函数，无 I/O）"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.modules.price_template.constants import (
    DEFAULT_DISCOUNT_RATE,
    MONEY_PRECISION,
)
from app.modules.product.constants import InputType
from app.modules.supplier.schemas.upstream import UpstreamBuyParam


def calc_sync_fixed_price(*, cost_price: Decimal) -> Decimal:
    """同步商品固定售价：成本价 × 默认折扣率（1.5 倍），按金额精度四舍五入"""
    return (cost_price * DEFAULT_DISCOUNT_RATE).quantize(
        MONEY_PRECISION,
        rounding=ROUND_HALF_UP,
    )


def build_buy_params(params: list[UpstreamBuyParam]) -> list[dict[str, Any]]:
    """将上游购买参数契约转为本地 ProductBuyParam 字段字典"""
    result: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for param in params:
        key = param.key
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        input_type = (
            InputType.LINK_EXTRACT if param.input_type == 61 else InputType.TEXT
        )
        result.append(
            {
                "key": key,
                "label": param.label,
                "value": param.value,
                "description": param.description,
                "input_type": input_type,
                "type_config": param.type_config,
                "default_value": param.default_value,
                "use_default": param.use_default,
                "is_required": True,
                "is_hidden": False,
                "is_edit": True,
                "validate_min": param.validate_min,
                "validate_max": param.validate_max,
            }
        )
    return result


def normalize_quantity_limits(
    *, min_quantity: int, max_quantity: int
) -> tuple[int, int]:
    """规范化购买数量边界：最小 ≥1、最大 ≥1 且 ≥ 最小"""
    min_quantity = max(min_quantity, 1)
    max_quantity = max(max_quantity, 1)
    if max_quantity < min_quantity:
        max_quantity = min_quantity
    return min_quantity, max_quantity
