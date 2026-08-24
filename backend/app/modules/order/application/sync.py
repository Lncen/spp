"""订单模块：上游订单状态同步与退单申请编排

流程编排在本模块；状态映射/退款规则在 order 模块，
上游能力调用在 supplier.application.upstream_order。
退单申请由 automation 事件触发（apply_supplier_refund 执行器调用本服务）。
"""

import uuid
from datetime import datetime

from sqlmodel import Session

from app.core.time import get_datetime_cn
from app.modules.order.application.after_sale.refund import auto_refund_order
from app.modules.order.application.order_state import (
    resolve_supplier_id,
    to_order_status,
)
from app.modules.order.domain.constants import SYNCABLE_ORDER_STATUSES, OrderStatus
from app.modules.order.models import Order
from app.modules.product.constants import RedeemType
from app.modules.supplier.application.upstream_order import (
    apply_upstream_refund,
    normalize_upstream_id,
    query_upstream_orders_status,
)
from app.modules.supplier.infrastructure.clients.base import SupplierClientError
from app.modules.supplier.models import Supplier
from app.modules.supplier.schemas.upstream import UpstreamOrder


def _syncable_orders(db_orders: list[Order]) -> list[Order]:
    """过滤出可同步上游状态的订单"""
    return [
        db_order
        for db_order in db_orders
        if db_order.status in SYNCABLE_ORDER_STATUSES
        and db_order.fulfillment_type == RedeemType.AUTO_API
        and db_order.supplier_order_id
    ]


def _query_upstream_orders(
    *, session: Session, orders: list[Order]
) -> dict[uuid.UUID, UpstreamOrder]:
    """按供应商分组批量查询上游订单，返回 {本地订单ID: UpstreamOrder}"""
    by_supplier: dict[uuid.UUID, list[Order]] = {}
    for db_order in orders:
        supplier_id = resolve_supplier_id(session=session, db_order=db_order)
        if supplier_id is None:
            raise SupplierClientError(
                f"订单 {db_order.order_no} 商品未配置供应商"
            )
        by_supplier.setdefault(supplier_id, []).append(db_order)

    upstream_by_order: dict[uuid.UUID, UpstreamOrder] = {}
    for supplier_id, group in by_supplier.items():
        upstream_order_ids = [
            db_order.supplier_order_id
            for db_order in group
            if db_order.supplier_order_id
        ]
        statuses = query_upstream_orders_status(
            session=session,
            supplier_id=supplier_id,
            upstream_order_ids=upstream_order_ids,
        )
        for db_order in group:
            upstream = statuses.get(
                normalize_upstream_id(db_order.supplier_order_id)
            )
            if upstream is None:
                raise SupplierClientError(
                    f"上游未返回订单 {db_order.supplier_order_id} 状态"
                )
            upstream_by_order[db_order.id] = upstream
    return upstream_by_order


def _apply_upstream_statuses(
    *,
    session: Session,
    syncable: list[Order],
    upstream_orders: dict[uuid.UUID, UpstreamOrder],
    now: datetime,
) -> bool:
    """按上游状态更新本地订单快照，退单/退款走自动退款，返回是否有变更"""
    changed = False
    for db_order in syncable:
        upstream = upstream_orders[db_order.id]
        db_order.start_quantity = upstream.start_num
        db_order.current_quantity = upstream.current_num
        new_status = to_order_status(db_order.supplier_order_id, upstream.status)
        if new_status in (OrderStatus.CANCELED, OrderStatus.REFUNDED):
            changed = (
                auto_refund_order(
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
    return changed


def sync_orders_status(*, session: Session, db_orders: list[Order]) -> list[Order]:
    """批量同步上游订单状态：更新数量快照，退单完成后自动按公式退款入账"""
    syncable = _syncable_orders(db_orders)
    if not syncable:
        return []
    before_quantities = {
        db_order.id: (db_order.start_quantity, db_order.current_quantity)
        for db_order in syncable
    }
    upstream_orders = _query_upstream_orders(
        session=session, orders=syncable
    )
    now = get_datetime_cn()
    changed = _apply_upstream_statuses(
        session=session,
        syncable=syncable,
        upstream_orders=upstream_orders,
        now=now,
    )
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


def apply_refund_application(*, session: Session, db_order: Order) -> None:
    """对已申请退单的 API 订单调用上游退单申请，成功后状态转为退单中

    由 automation 执行器（apply_supplier_refund）调用；条件不成立时直接返回，
    上游调用以 (supplier_id, upstream_order_id) 定位，避免多供应商同上游订单号歧义；
    供应商缺失或上游调用失败抛 SupplierClientError，订单保持 APPLYING_AFTER_SALE，
    由任务池按 max_retry 重试；上游明确业务性拒绝抛 SupplierClientRejectedError，
    由执行器直接转为失败终态供人工处理。
    """
    upstream_order_id = db_order.supplier_order_id or ""
    if (
        db_order.status != OrderStatus.APPLYING_AFTER_SALE
        or not db_order.can_refund
        or db_order.fulfillment_type != RedeemType.AUTO_API
        or not upstream_order_id
    ):
        return
    supplier_id = resolve_supplier_id(session=session, db_order=db_order)
    if supplier_id is None:
        raise SupplierClientError(f"订单 {db_order.order_no} 商品未配置供应商")
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise SupplierClientError(f"订单 {db_order.order_no} 供应商不存在")
    apply_upstream_refund(
        session=session,
        supplier_id=supplier_id,
        upstream_order_id=upstream_order_id,
    )
    db_order.status = OrderStatus.REFUNDING
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
