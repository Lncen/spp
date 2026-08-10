"""订单模块：下单领域校验规则"""

import json
import uuid
from decimal import Decimal
from typing import Any

from fastapi import HTTPException

from app.modules.order.domain.constants import SALABLE_PRODUCT_STATUSES
from app.modules.product.product.models import (
    Product,
    ProductBuyParam,
    ProductFulfillment,
    ProductInventory,
)


def _generate_order_no() -> str:
    """生成唯一订单号"""
    return uuid.uuid4().hex.upper()


def _validate_product_sellable(
    *, product: Product, inventory: ProductInventory, fulfillment: ProductFulfillment
) -> None:
    """校验商品可售状态与配置完整性"""
    if not product.is_active:
        raise HTTPException(status_code=400, detail="商品已停用")
    if product.is_closed:
        raise HTTPException(status_code=400, detail="商品已关闭下单")
    if product.status not in SALABLE_PRODUCT_STATUSES:
        raise HTTPException(status_code=400, detail="商品当前不可购买")
    if inventory is None or fulfillment is None:
        raise HTTPException(status_code=400, detail="商品配置不完整")


def _validate_quantity(*, inventory: ProductInventory, quantity: int) -> None:
    """校验购买数量满足商品库存限制"""
    if quantity < inventory.min_quantity:
        raise HTTPException(
            status_code=400,
            detail=f"购买数量不能小于最小购买数量 {inventory.min_quantity}",
        )
    if quantity > inventory.max_quantity:
        raise HTTPException(
            status_code=400,
            detail=f"购买数量不能大于最大购买数量 {inventory.max_quantity}",
        )
    if not inventory.is_batch and quantity > 1:
        raise HTTPException(status_code=400, detail="该商品不支持批量购买")
    if Decimal(quantity) % inventory.purchase_step != 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"购买数量必须是 {str(inventory.purchase_step.normalize())} 的整数倍"
            ),
        )
def _validate_and_build_params(
    *,
    params: dict[str, Any] | None,
    buy_params: list[ProductBuyParam],
) -> dict[str, Any]:
    """按商品购买参数定义补齐并校验下单参数"""
    values: dict[str, Any] = {}
    provided = params or {}
    for param in buy_params:
        if param.use_default:
            values[param.key] = param.default_value
            continue
        value = provided.get(param.key)
        if param.is_required and value in (None, ""):
            raise HTTPException(
                status_code=400,
                detail=f"缺少必填下单参数: {param.label}",
            )
        if value is not None:
            values[param.key] = value
    return values


def normalize_param_value(value: Any) -> str:
    """参数值统一转字符串比较，复合类型用 JSON 稳定序列化"""
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _normalize_params(params: dict[str, Any] | None) -> dict[str, str]:
    """参数按 key 排序后统一序列化，用于重复下单比较"""
    return {
        str(key): normalize_param_value(value)
        for key, value in sorted((params or {}).items())
    }
