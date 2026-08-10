"""订单模块：订单状态同步应用服务"""

import logging
import uuid
from datetime import UTC, datetime

from sqlmodel import Session

from app.modules.order.application.refund import auto_refund_order
from app.modules.order.domain.constants import SYNCABLE_ORDER_STATUSES, OrderStatus
from app.modules.order.infrastructure.sync import (
    _resolve_supplier_id,
    query_api_orders_status,
)
from app.modules.order.models import Order
from app.modules.product.constants import RedeemType
from app.modules.supplier.models import Supplier
from app.modules.supplier.service.clients.base import (
    SupplierClientBase,
    SupplierClientError,
)

logger = logging.getLogger(__name__)


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
        supplier_id = _resolve_supplier_id(
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


def _syncable_orders(db_orders: list[Order]) -> list[Order]:
    """过滤出可同步上游状态的订单"""
    return [
        db_order
        for db_order in db_orders
        if db_order.status in SYNCABLE_ORDER_STATUSES
        and db_order.fulfillment_type == RedeemType.AUTO_API
        and db_order.supplier_order_id
    ]


def _apply_upstream_statuses(
    *,
    session: Session,
    syncable: list[Order],
    statuses: dict[uuid.UUID, OrderStatus],
    now: datetime,
) -> bool:
    """按上游状态更新本地订单快照，退单/退款走自动退款，返回是否有变更"""
    changed = False
    for db_order in syncable:
        new_status = statuses[db_order.id]
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
    statuses = query_api_orders_status(session=session, db_orders=syncable)
    now = datetime.now(UTC)
    changed = _apply_upstream_statuses(
        session=session,
        syncable=syncable,
        statuses=statuses,
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
