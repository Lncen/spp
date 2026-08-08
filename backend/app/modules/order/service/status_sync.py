"""订单上游状态批量同步"""

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlmodel import Session, select

from app.modules.order.constants import OrderStatus
from app.modules.order.models import Order
from app.modules.order.service.validation import (
    _calc_refund_amount,
    _restore_stock,
)
from app.modules.product.constants import RedeemType
from app.modules.product.product.models import ProductSupplier
from app.modules.supplier.models import Supplier
from app.modules.supplier.service.clients.base import (
    SupplierClientBase,
    SupplierClientError,
)
from app.modules.supplier.service.dto import UpstreamOrder
from app.modules.wallet.service import adjust_balance, get_wallet_by_user_id

logger = logging.getLogger(__name__)


# 可同步上游状态的订单状态（终态订单无需再查询）
SYNCABLE_ORDER_STATUSES = frozenset(
    {
        # OrderStatus.PAID,
        OrderStatus.PENDING,
        OrderStatus.PROCESSING,
        OrderStatus.SUPPLEMENTING,
        OrderStatus.REFUNDING,
        OrderStatus.EXCEPTION,
        OrderStatus.APPLYING_AFTER_SALE,
    }
)

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


def _query_api_orders_status(
    *,
    session: Session,
    db_orders: list[Order],
) -> dict[uuid.UUID, OrderStatus]:
    """按供应商分组批量查询上游订单状态，返回 {订单ID: 本地状态}"""
    by_supplier: dict[uuid.UUID, list[Order]] = {}
    for db_order in db_orders:
        supplier_id = db_order.supplier_id
        if supplier_id is None:
            # 旧订单未落货源快照时回退查询商品当前货源
            supplier_sku = session.exec(
                select(ProductSupplier).where(
                    ProductSupplier.product_id == db_order.product_id
                )
            ).first()
            if supplier_sku is None or supplier_sku.supplier_id is None:
                raise SupplierClientError(
                    f"订单 {db_order.order_no} 商品未配置供应商"
                )
            supplier_id = supplier_sku.supplier_id
        by_supplier.setdefault(supplier_id, []).append(db_order)

    statuses: dict[uuid.UUID, OrderStatus] = {}
    for supplier_id, orders in by_supplier.items():
        supplier = session.get(Supplier, supplier_id)
        if not supplier:
            raise SupplierClientError("供应商不存在")
        with SupplierClientBase.get_client(supplier) as client:
            upstream = client.query_order(
                [db_order.supplier_order_id for db_order in orders]
            )
        if len(orders) == 1 and isinstance(upstream, dict):
            # 兼容单订单 dict 返回（旧格式/测试 mock），不依赖 id 映射
            raw_status = _extract_upstream_status(upstream)
            if raw_status is None:
                raise SupplierClientError(
                    f"上游订单 {orders[0].supplier_order_id} 缺少状态字段"
                )
            statuses[orders[0].id] = _to_order_status(
                orders[0].supplier_order_id, raw_status
            )
            continue
        status_by_upstream = {
            item.upstream_id: item
            for item in upstream
            if isinstance(item, UpstreamOrder)
        }
        for db_order in orders:
            upstream_id = str(int(db_order.supplier_order_id))
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
    return statuses


def _resolve_refund_supplier_id(
    *, session: Session, db_order: Order
) -> uuid.UUID | None:
    """解析退单所用供应商：优先订单快照，旧订单回退查商品货源"""
    if db_order.supplier_id is not None:
        return db_order.supplier_id
    supplier_sku = session.exec(
        select(ProductSupplier).where(
            ProductSupplier.product_id == db_order.product_id
        )
    ).first()
    return supplier_sku.supplier_id if supplier_sku else None


def apply_refund_applications(*, session: Session, db_orders: list[Order]) -> None:
    """对已申请退单的 API 订单调用上游退单申请，成功后状态转为退单中"""
    for db_order in db_orders:
        if (
            db_order.status != OrderStatus.APPLYING_AFTER_SALE
            or not db_order.can_refund
            or db_order.fulfillment_type != RedeemType.AUTO_API
            or not db_order.supplier_order_id
        ):
            continue
        supplier_id = _resolve_refund_supplier_id(
            session=session, db_order=db_order
        )
        if supplier_id is None:
            logger.warning("订单 %s 未配置供应商，跳过上游退单申请", db_order.order_no)
            continue
        supplier = session.get(Supplier, supplier_id)
        if not supplier:
            logger.warning("订单 %s 供应商不存在，跳过上游退单申请", db_order.order_no)
            continue
        try:
            with SupplierClientBase.get_client(supplier) as client:
                client.cancel_order(db_order.supplier_order_id)
        except SupplierClientError as exc:
            logger.warning("订单 %s 上游退单申请失败: %s", db_order.order_no, exc)
            continue
        db_order.status = OrderStatus.REFUNDING
        session.add(db_order)
    session.commit()


def _auto_refund_order(
    *, session: Session, db_order: Order, upstream_status: OrderStatus
) -> bool:
    """上游已退单/已退款时按公式自动退款入账，非已完成订单回补库存"""
    if db_order.refunded_at is not None or db_order.status == OrderStatus.REFUNDED:
        return False
    amount = _calc_refund_amount(db_order=db_order)
    if amount > Decimal("0"):
        wallet = get_wallet_by_user_id(session=session, user_id=db_order.user_id)
        if not wallet:
            raise SupplierClientError(f"订单 {db_order.order_no} 用户钱包不存在")
        adjust_balance(
            session=session,
            wallet=wallet,
            amount=amount,
            tx_type="refund",
            ref_type="order",
            ref_id=db_order.id,
            remark=f"订单 {db_order.order_no} 上游退单自动退款",
            operator_id=None,
            commit=False,
        )
    if db_order.status != OrderStatus.COMPLETED:
        _restore_stock(
            session=session,
            product_id=db_order.product_id,
            quantity=db_order.quantity,
        )
    db_order.status = OrderStatus.REFUNDED
    db_order.refunded_at = datetime.now(UTC)
    if upstream_status == OrderStatus.CANCELED:
        db_order.canceled_at = datetime.now(UTC)
    session.add(db_order)
    return True


def sync_orders_status(*, session: Session, db_orders: list[Order]) -> list[Order]:
    """批量同步上游订单状态：更新数量快照，退单完成后自动按公式退款入账"""
    syncable = [
        db_order
        for db_order in db_orders
        if db_order.status in SYNCABLE_ORDER_STATUSES
        and db_order.fulfillment_type == RedeemType.AUTO_API
        and db_order.supplier_order_id
    ]
    if not syncable:
        return []
    before_quantities = {
        db_order.id: (db_order.start_quantity, db_order.current_quantity)
        for db_order in syncable
    }
    statuses = _query_api_orders_status(session=session, db_orders=syncable)
    now = datetime.now(UTC)
    changed = False
    for db_order in syncable:
        new_status = statuses[db_order.id]
        if new_status in (OrderStatus.CANCELED, OrderStatus.REFUNDED):
            changed = (
                _auto_refund_order(
                    session=session,
                    db_order=db_order,
                    upstream_status=new_status,
                )
                or changed
            )
            continue
        if new_status == db_order.status:
            continue
        db_order.status = new_status
        if new_status == OrderStatus.COMPLETED:
            db_order.completed_at = now
        session.add(db_order)
        changed = True
    for db_order in syncable:
        if before_quantities[db_order.id] != (
            db_order.start_quantity,
            db_order.current_quantity,
        ):
            session.add(db_order)
            changed = True
    if changed:
        session.commit()
        for db_order in syncable:
            session.refresh(db_order)
    return syncable
