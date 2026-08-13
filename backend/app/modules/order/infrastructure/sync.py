"""订单模块：上游订单状态查询基础设施"""

import logging
import uuid
from typing import Any

from sqlmodel import Session, select

from app.modules.order.domain.constants import OrderStatus
from app.modules.order.models import Order
from app.modules.product.product.models import ProductSupplier
from app.modules.supplier.infrastructure.clients.base import (
    SupplierClientBase,
    SupplierClientError,
)
from app.modules.supplier.models import Supplier
from app.modules.supplier.schemas.upstream import UpstreamOrder

logger = logging.getLogger(__name__)


def _extract_upstream_status(result: Any) -> int | None:
    """从上游订单查询结果中提取状态数字"""
    if isinstance(result, list):
        if not result:
            return None
        first = result[0]
        if isinstance(first, UpstreamOrder):
            return first.status
        data = first if isinstance(first, dict) else {}
    elif isinstance(result, dict):
        data = (
            result.get("data") if isinstance(result.get("data"), (dict, list)) else result
        )
        if isinstance(data, list):
            data = data[0] if data and isinstance(data[0], dict) else {}
    else:
        return None
    if not isinstance(data, dict):
        return None
    for key in ("status", "order_status", "state"):
        value = data.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


def _to_order_status(upstream_order_id: str | None, raw_status: int) -> OrderStatus:
    """上游状态数字转为本地 OrderStatus，未知值抛异常"""
    try:
        return OrderStatus(raw_status)
    except ValueError as exc:
        raise SupplierClientError(
            f"上游订单 {upstream_order_id} 返回未知状态 {raw_status}"
        ) from exc


def _resolve_supplier_id(
    *, session: Session, db_order: Order
) -> uuid.UUID | None:
    """解析订单供应商：优先订单快照，旧订单回退查商品当前货源，未配置返回 None"""
    if db_order.supplier_id is not None:
        return db_order.supplier_id
    supplier_sku = session.exec(
        select(ProductSupplier).where(
            ProductSupplier.product_id == db_order.product_id
        )
    ).first()
    return supplier_sku.supplier_id if supplier_sku else None


def _parse_single_dict_status(
    *, orders: list[Order], upstream: dict[str, Any]
) -> tuple[uuid.UUID, OrderStatus]:
    """兼容单订单 dict 返回（旧格式/测试 mock），返回订单 ID 与本地状态"""
    raw_status = _extract_upstream_status(upstream)
    if raw_status is None:
        raise SupplierClientError(
            f"上游订单 {orders[0].supplier_order_id} 缺少状态字段"
        )
    return orders[0].id, _to_order_status(
        orders[0].supplier_order_id, raw_status
    )


def _query_supplier_group(
    *,
    session: Session,
    supplier_id: uuid.UUID,
    orders: list[Order],
    statuses: dict[uuid.UUID, OrderStatus],
) -> None:
    """查询单个供应商的订单状态并写入 statuses（兼容单订单 dict 返回）

    顺序执行的简单流水线（查询上游、解析状态与回写数量），按 AGENTS.md 放宽至 60 行。
    """
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise SupplierClientError("供应商不存在")
    with SupplierClientBase.get_client(supplier) as client:
        upstream = client.query_order(
            [db_order.supplier_order_id for db_order in orders]
        )
    if len(orders) == 1 and isinstance(upstream, dict):
        order_id, status = _parse_single_dict_status(
            orders=orders, upstream=upstream
        )
        statuses[order_id] = status
        return
    status_by_upstream = {
        item.upstream_id: item
        for item in upstream
        if isinstance(item, UpstreamOrder)
    }
    for db_order in orders:
        try:
            upstream_id = str(int(db_order.supplier_order_id))
        except (TypeError, ValueError):
            upstream_id = str(db_order.supplier_order_id)
        if upstream_id not in status_by_upstream:
            raise SupplierClientError(
                f"上游未返回订单 {db_order.supplier_order_id} 状态"
            )
        upstream_order = status_by_upstream[upstream_id]
        db_order.start_quantity = upstream_order.start_num
        db_order.current_quantity = upstream_order.current_num
        statuses[db_order.id] = _to_order_status(
            db_order.supplier_order_id, upstream_order.status
        )


def query_api_orders_status(
    *,
    session: Session,
    db_orders: list[Order],
) -> dict[uuid.UUID, OrderStatus]:
    """按供应商分组批量查询上游订单状态，返回 {订单ID: 本地状态}"""
    by_supplier: dict[uuid.UUID, list[Order]] = {}
    for db_order in db_orders:
        supplier_id = _resolve_supplier_id(session=session, db_order=db_order)
        if supplier_id is None:
            raise SupplierClientError(
                f"订单 {db_order.order_no} 商品未配置供应商"
            )
        by_supplier.setdefault(supplier_id, []).append(db_order)

    statuses: dict[uuid.UUID, OrderStatus] = {}
    for supplier_id, orders in by_supplier.items():
        _query_supplier_group(
            session=session,
            supplier_id=supplier_id,
            orders=orders,
            statuses=statuses,
        )
    return statuses
