"""供应商模块：上游订单能力服务（下单/查单/退单）

只封装上游 API 调用与结果归一化，不含业务规则；
异常语义与 client 一致：
- SupplierClientError：明确失败，可安全重试；
- SupplierClientUnknownError：结果未知（超时/断连/未返回订单号），需人工确认。
"""

import uuid
from typing import Any

from sqlmodel import Session

from app.modules.supplier.infrastructure.clients.base import (
    SupplierClientError,
    SupplierClientUnknownError,
    supplier_client,
)
from app.modules.supplier.schemas.upstream import UpstreamOrder


def normalize_upstream_id(value: Any) -> str:
    """上游订单号统一为字符串，兼容数字与带前导零的字符串"""
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def submit_upstream_order(
    *,
    session: Session,
    supplier_id: uuid.UUID,
    sku_id: str,
    quantity: int,
    params: dict[str, Any] | None = None,
    customer_order_id: str | None = None,
) -> str:
    """向上游提交订单，返回上游订单号。"""
    call_kwargs: dict[str, Any] = {
        "product_id": sku_id,
        "quantity": quantity,
        **(params or {}),
    }
    if customer_order_id:
        call_kwargs["customer_order_id"] = customer_order_id
    with supplier_client(session=session, supplier_id=supplier_id) as client:
        result = client.create_order(**call_kwargs)
    # 契约返回上游原始 dict，提取订单号；兼容返回标量的平台客户端
    order_id = result.get("order_id") if isinstance(result, dict) else result
    if order_id is None:
        raise SupplierClientUnknownError(
            "上游下单成功但未返回订单号，需人工确认"
        )
    return str(order_id)


def query_upstream_orders_status(
    *,
    session: Session,
    supplier_id: uuid.UUID,
    upstream_order_ids: list[str],
) -> dict[str, UpstreamOrder]:
    """批量查询上游订单状态，返回 {上游订单号: UpstreamOrder}。"""
    with supplier_client(session=session, supplier_id=supplier_id) as client:
        upstream = client.query_order(upstream_order_ids)
    result: dict[str, UpstreamOrder] = {}
    for item in upstream or []:
        if isinstance(item, UpstreamOrder):
            result[normalize_upstream_id(item.upstream_id)] = item
    missing = [
        order_id
        for order_id in upstream_order_ids
        if normalize_upstream_id(order_id) not in result
    ]
    if missing:
        raise SupplierClientError(f"上游未返回订单 {missing[0]} 状态")
    return result


def apply_upstream_refund(
    *,
    session: Session,
    supplier_id: uuid.UUID,
    upstream_order_id: str,
) -> None:
    """向上游申请退单；失败抛 SupplierClientError。"""
    with supplier_client(session=session, supplier_id=supplier_id) as client:
        client.cancel_order(upstream_order_id)
