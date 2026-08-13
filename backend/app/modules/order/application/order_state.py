"""订单模块：履约相关状态转换规则

由 automation 编排调用；本模块不直接访问上游 API，
上游能力调用在 supplier.application.upstream_order。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlmodel import Session, select

from app.modules.order.domain.constants import OrderStatus
from app.modules.order.infrastructure.notification import notify_order_exception
from app.modules.order.models import Order
from app.modules.product.constants import RedeemType
from app.modules.product.product.models import ProductSupplier
from app.modules.supplier.infrastructure.clients.base import SupplierClientError
from app.modules.supplier.models import Supplier


def resolve_supplier_id(*, session: Session, db_order: Order) -> uuid.UUID | None:
    """解析订单供应商：优先订单快照，旧订单回退查商品当前货源，未配置返回 None"""
    if db_order.supplier_id is not None:
        return db_order.supplier_id
    supplier_sku = session.exec(
        select(ProductSupplier).where(
            ProductSupplier.product_id == db_order.product_id
        )
    ).first()
    return supplier_sku.supplier_id if supplier_sku else None


def resolve_fulfill_target(
    *, session: Session, db_order: Order
) -> tuple[uuid.UUID, str]:
    """解析履约供应商与 SKU：订单快照优先，旧订单回退查商品当前货源"""
    supplier_id, sku_id = db_order.supplier_id, db_order.sku_id
    if supplier_id is None or not sku_id:
        supplier_sku = session.exec(
            select(ProductSupplier).where(
                ProductSupplier.product_id == db_order.product_id
            )
        ).first()
        if (
            supplier_sku is None
            or supplier_sku.supplier_id is None
            or not supplier_sku.sku_id
        ):
            raise SupplierClientError("商品未配置供应商或 SKU")
        supplier_id, sku_id = supplier_sku.supplier_id, supplier_sku.sku_id
    supplier = session.get(Supplier, supplier_id)
    if not supplier:
        raise SupplierClientError("供应商不存在")
    return supplier_id, sku_id


def claim_order(*, session: Session, db_order: Order) -> bool:
    """原子认领订单（PAID → PROCESSING），防止并发重复履约"""
    now = datetime.now(UTC)
    result = session.exec(
        update(Order)
        .where(
            Order.id == db_order.id,
            Order.status == OrderStatus.PAID,
            Order.supplier_order_id.is_(None),
        )
        .values(status=OrderStatus.PROCESSING, processing_at=now)
    )
    claimed = result.rowcount == 1
    session.commit()
    if claimed:
        session.refresh(db_order)
    return claimed


def record_upstream_order_created(*, db_order: Order, supplier_order_id: str) -> None:
    """回写上游订单号并置为处理中（不提交）"""
    db_order.supplier_order_id = supplier_order_id
    db_order.status = OrderStatus.PROCESSING


def rollback_claim_on_failure(
    *,
    session: Session,
    db_order: Order,
    now: datetime,
    fail_limit: int,
) -> None:
    """明确失败：回滚认领为已付款，累计失败次数，达阈值标记异常"""
    db_order.status = OrderStatus.PAID
    db_order.fulfill_failed_count = (db_order.fulfill_failed_count or 0) + 1
    if db_order.fulfill_failed_count >= fail_limit:
        db_order.status = OrderStatus.EXCEPTION
        db_order.failed_at = now
        note = f"履约连续失败 {db_order.fulfill_failed_count} 次，已标记异常"
        db_order.remark = (
            f"{db_order.remark}；{note}"[:255] if db_order.remark else note
        )
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    if db_order.status == OrderStatus.EXCEPTION:
        notify_order_exception(db_order=db_order)


def mark_unknown_outcome(*, session: Session, db_order: Order) -> None:
    """结果未知：标记异常转人工确认，不自动重试"""
    db_order.status = OrderStatus.EXCEPTION
    db_order.failed_at = datetime.now(UTC)
    note = "履约结果未知，需人工确认上游是否已下单"
    db_order.remark = (
        f"{db_order.remark}；{note}"[:255] if db_order.remark else note
    )
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    notify_order_exception(db_order=db_order)


def finalize_fulfillment(
    *,
    db_order: Order,
    is_api: bool,
    now: datetime,
    upstream_status: OrderStatus | None = None,
) -> None:
    """上游下单成功后回写最终状态（不提交）"""
    if db_order.fulfillment_type == RedeemType.MANUAL:
        db_order.status = OrderStatus.PROCESSING
    elif not is_api:
        db_order.status = OrderStatus.COMPLETED
        db_order.completed_at = now
    elif upstream_status is not None:
        db_order.status = upstream_status
        if upstream_status == OrderStatus.COMPLETED:
            db_order.completed_at = now
    else:
        # 上游订单已创建，状态查询失败保持 PENDING，由状态同步任务后续处理
        db_order.status = OrderStatus.PENDING


def to_order_status(upstream_order_id: str | None, raw_status: int) -> OrderStatus:
    """上游状态数字转为本地 OrderStatus，未知值抛异常"""
    try:
        return OrderStatus(raw_status)
    except ValueError as exc:
        raise SupplierClientError(
            f"上游订单 {upstream_order_id} 返回未知状态 {raw_status}"
        ) from exc
