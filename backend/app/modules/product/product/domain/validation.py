"""商品模块：商品领域校验规则（纯业务规则，不依赖数据库）"""

from typing import Any

from fastapi import HTTPException


def validate_buy_param_keys(*, params: list[Any]) -> None:
    """校验下单参数 key 非空且不重复"""
    keys = [param.key for param in params]
    if any(key is None for key in keys):
        raise HTTPException(status_code=400, detail="购买参数 key 不能为空")
    if len(keys) != len(set(keys)):
        raise HTTPException(status_code=400, detail="购买参数 key 不能重复")


def validate_single_price_rule(
    *,
    price_template_id: Any,
    fixed_price: Any,
    item_coefficient: Any,
) -> None:
    """校验固定价格、商品系数、价格模板三者必须且只能设置一个"""
    filled_count = sum(
        1
        for value in (price_template_id, fixed_price, item_coefficient)
        if value is not None
    )
    if filled_count != 1:
        raise HTTPException(
            status_code=400,
            detail="固定价格、商品系数、价格模板三者必须且只能设置一个",
        )


def validate_quantity_bounds(*, min_quantity: int, max_quantity: int) -> None:
    """校验最小购买数量不能大于最大购买数量"""
    if min_quantity > max_quantity:
        raise HTTPException(status_code=400, detail="最小购买数量不能大于最大购买数量")
