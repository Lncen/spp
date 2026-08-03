"""ylsup 上游商品数据转换器

职责：上游原始 dict -> service/dto.py 定义的共享契约，
不接触本地数据库模型，不做定价等本地业务决策。
"""

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from app.modules.supplier.service.dto import (
    UpstreamBuyParam,
    UpstreamProductDetail,
    UpstreamProductSummary,
)


def _parse_decimal(value: Any, field: str) -> Decimal:
    """解析上游数字字段，失败时抛出带字段名的异常"""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise ValueError(f"上游字段 {field} 无法解析为数字: {value!r}") from e


def _parse_int(value: Any, default: int) -> int:
    """解析上游整数字段，非法值回退默认值"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_type_config(value: Any) -> list[dict[str, Any]]:
    """解析上游 type_config，字符串 JSON 解析失败时返回空列表"""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _buy_params(raw_params: Any) -> list[UpstreamBuyParam]:
    """上游 buy_params -> UpstreamBuyParam"""
    result: list[UpstreamBuyParam] = []
    for param in raw_params or []:
        if not isinstance(param, dict):
            continue
        key = str(param.get("key") or "").strip()
        if not key:
            continue
        verify = param.get("verify")
        verify = verify if isinstance(verify, dict) else {}
        result.append(
            UpstreamBuyParam(
                key=key,
                label=str(param.get("label") or param.get("name") or key),
                value=str(param.get("value") or ""),
                description=str(param.get("description") or ""),
                input_type=_parse_int(param.get("type"), 0),
                type_config=_parse_type_config(param.get("type_config")),
                validate_min=max(_parse_int(verify.get("min"), 0), 0),
                validate_max=max(_parse_int(verify.get("max"), 0), 0),
                default_value=str(param.get("value") or ""),
                use_default=bool(param.get("is_default")),
            )
        )
    return result


def yl_product_summary_adapter(raw: dict[str, Any]) -> UpstreamProductSummary:
    """上游商品列表项 -> UpstreamProductSummary"""
    upstream_id = raw.get("id")
    if upstream_id in (None, ""):
        raise ValueError("上游商品列表项缺少 id 字段")
    price_raw = raw.get("price")
    cost_price = None
    if price_raw not in (None, ""):
        cost_price = _parse_decimal(price_raw, "price")
    return UpstreamProductSummary(
        upstream_id=str(upstream_id),
        name=str(raw.get("name") or ""),
        cost_price=cost_price,
    )


def yl_goods_adapter(raw: dict[str, Any]) -> UpstreamProductDetail:
    """上游商品详情 -> UpstreamProductDetail"""
    upstream_id = raw.get("id")
    if upstream_id in (None, ""):
        raise ValueError("上游商品详情缺少 id 字段")
    price_raw = raw.get("price")
    if price_raw in (None, ""):
        raise ValueError("上游商品详情缺少 price 字段")

    min_quantity = max(_parse_int(raw.get("buy_min_limit"), 1), 1)
    max_quantity = max(_parse_int(raw.get("buy_max_limit"), 1_000_000), 1)
    if max_quantity < min_quantity:
        max_quantity = min_quantity

    return UpstreamProductDetail(
        upstream_id=str(upstream_id),
        name=str(raw.get("name") or ""),
        cost_price=_parse_decimal(price_raw, "price"),
        stock=max(_parse_int(raw.get("stock"), -1), -1),
        min_quantity=min_quantity,
        max_quantity=max_quantity,
        # purchase_step: 上游未提供步长字段，保持契约默认值 1
        is_repeatable=(
            _parse_int(raw.get("is_repeat"), 0) == 2
        ),  # TODO: 确认上游 is_repeat 语义
        is_batch=_parse_int(raw.get("is_batch"), 1) == 1,
        is_card_code=_parse_int(raw.get("is_card_code"), 0) == 1,
        is_closed=_parse_int(raw.get("is_close"), 1) == 2,
        can_refund=bool(raw.get("refund_status")),
        unit=str(raw.get("unit") or "1"),
        description=str(raw.get("particulars") or ""),
        image_urls=[str(url) for url in (raw.get("image_urls") or [])],
        buy_params=_buy_params(raw.get("buy_params")),
    )
