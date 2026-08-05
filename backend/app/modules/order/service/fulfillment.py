"""订单模块：履约与状态同步"""

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.modules.order.constants import OrderStatus
from app.modules.order.models import Order
from app.modules.order.service.validation import _restore_stock
from app.modules.product.constants import RedeemType
from app.modules.product.product.models import ProductSupplier
from app.modules.supplier.models import Supplier
from app.modules.supplier.service.clients.base import (
    SupplierClientBase,
    SupplierClientError,
)
from app.modules.wallet.service import adjust_balance, get_wallet_by_user_id

logger = logging.getLogger(__name__)


def _refund_order(
    *,
    session: Session,
    db_order: Order,
    amount: Decimal,
    operator_id: Any = None,
) -> None:
    """按指定金额退款入账，只写流水不提交"""
    wallet = get_wallet_by_user_id(session=session, user_id=db_order.user_id)
    if not wallet:
        raise HTTPException(status_code=400, detail="钱包不存在")
    adjust_balance(
        session=session,
        wallet=wallet,
        amount=amount,
        tx_type="refund",
        ref_type="order",
        ref_id=db_order.id,
        remark=f"订单 {db_order.order_no} 退款",
        operator_id=operator_id,
        commit=False,
    )


def cancel_order(
    *,
    session: Session,
    db_order: Order,
    operator_id: uuid.UUID | None = None,
    enforce_refundable: bool = False,
) -> Order:
    """取消订单申请：状态置售后申请中，不退款不回补库存"""
    if db_order.status not in (
        OrderStatus.PAID,
        OrderStatus.PENDING,
        OrderStatus.PROCESSING,
    ):
        raise HTTPException(status_code=400, detail="当前状态不可取消")
    if enforce_refundable and not db_order.can_refund:
        raise HTTPException(status_code=400, detail="订单包含不支持退款的商品")
    now = datetime.now(UTC)
    db_order.status = OrderStatus.APPLYING_AFTER_SALE
    db_order.canceled_at = now
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order


def refund_order(
    *,
    session: Session,
    db_order: Order,
    amount: Decimal,
    operator_id: uuid.UUID | None = None,
) -> Order:
    """管理员手动退款：按指定金额入账，处理中或售后申请订单回补库存"""
    if db_order.status not in (
        OrderStatus.PROCESSING,
        OrderStatus.REFUNDING,
        OrderStatus.COMPLETED,
        OrderStatus.APPLYING_AFTER_SALE,
    ):
        raise HTTPException(status_code=400, detail="当前状态不可退款")
    if amount > db_order.total_amount:
        raise HTTPException(status_code=400, detail="退款金额不能超过订单金额")
    _refund_order(
        session=session,
        db_order=db_order,
        amount=amount,
        operator_id=operator_id,
    )
    if db_order.status in (
        OrderStatus.PROCESSING,
        OrderStatus.APPLYING_AFTER_SALE,
    ):
        _restore_stock(
            session=session,
            product_id=db_order.product_id,
            quantity=db_order.quantity,
        )
    db_order.status = OrderStatus.REFUNDED
    db_order.refunded_at = datetime.now(UTC)
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order


def _extract_supplier_order_id(result: dict[str, Any]) -> str | None:
    """从上游下单返回中提取供应商订单号"""
    payload = result.get("data") if isinstance(result.get("data"), dict) else result
    for key in ("order_id", "orderId", "id"):
        value = payload.get(key)
        if value is not None:
            return str(value)
    return None


def _extract_upstream_status(result: dict[str, Any]) -> int | None:
    """从上游订单查询结果中提取状态数字"""
    data = (
        result.get("data") if isinstance(result.get("data"), (dict, list)) else result
    )
    if isinstance(data, list):
        if not data:
            return None
        data = data[0] if isinstance(data[0], dict) else {}
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


def _merge_upstream_statuses(statuses: list[OrderStatus]) -> OrderStatus:
    """多商品项取最不利状态，异常与退单中优先于已完成"""
    priority = {
        OrderStatus.EXCEPTION: 0,
        OrderStatus.REFUNDING: 1,
        OrderStatus.SUPPLEMENTING: 2,
        OrderStatus.PENDING: 3,
        OrderStatus.PROCESSING: 4,
        OrderStatus.PAID: 5,
        OrderStatus.COMPLETED: 6,
        OrderStatus.CANCELED: 7,
        OrderStatus.REFUNDED: 8,
    }
    return min(statuses, key=lambda status: priority[status])


def _fulfill_api_item(*, session: Session, db_order: Order) -> None:
    """调用供应商 API 下单，写入供应商订单号"""
    supplier_sku = session.exec(
        select(ProductSupplier).where(ProductSupplier.product_id == db_order.product_id)
    ).first()
    if (
        supplier_sku is None
        or supplier_sku.supplier_id is None
        or not supplier_sku.sku_id
    ):
        raise SupplierClientError("商品未配置供应商或 SKU")
    supplier = session.get(Supplier, supplier_sku.supplier_id)
    if not supplier:
        raise SupplierClientError("供应商不存在")
    client = SupplierClientBase.get_client(supplier)
    try:
        result = client.create_order(
            product_id=supplier_sku.sku_id,
            quantity=db_order.quantity,
            **db_order.params,
        )
        db_order.supplier_order_id = _extract_supplier_order_id(result)
        session.add(db_order)
    finally:
        client.close()


def _query_api_item_status(*, session: Session, db_order: Order) -> OrderStatus:
    """查询上游订单状态并映射为本地订单状态"""
    supplier_sku = session.exec(
        select(ProductSupplier).where(ProductSupplier.product_id == db_order.product_id)
    ).first()
    if supplier_sku is None or supplier_sku.supplier_id is None:
        raise SupplierClientError("商品未配置供应商")
    supplier = session.get(Supplier, supplier_sku.supplier_id)
    if not supplier:
        raise SupplierClientError("供应商不存在")
    client = SupplierClientBase.get_client(supplier)
    try:
        result = client.query_order([int(db_order.supplier_order_id)])
    finally:
        client.close()
    raw_status = _extract_upstream_status(result)
    if raw_status is None:
        raise SupplierClientError(
            f"上游订单 {db_order.supplier_order_id} 缺少状态字段"
        )
    try:
        return OrderStatus(raw_status)
    except ValueError as exc:
        raise SupplierClientError(
            f"上游订单 {db_order.supplier_order_id} 返回未知状态 {raw_status}"
        ) from exc


def fulfill_order(
    *,
    session: Session,
    db_order: Order,
    operator_id: uuid.UUID | None = None,
) -> Order:
    """履约订单：自动完成、标记处理中或调用供应商 API 并同步上游状态"""
    if db_order.status != OrderStatus.PAID:
        raise HTTPException(status_code=400, detail="当前状态不可履约")

    now = datetime.now(UTC)
    db_order.processing_at = now
    is_api = db_order.fulfillment_type == RedeemType.AUTO_API

    try:
        if is_api:
            _fulfill_api_item(session=session, db_order=db_order)
    except SupplierClientError as exc:
        _restore_stock(
            session=session,
            product_id=db_order.product_id,
            quantity=db_order.quantity,
        )
        db_order.status = OrderStatus.REFUNDING
        db_order.failed_at = now
        session.add(db_order)
        session.commit()
        session.refresh(db_order)
        raise HTTPException(
            status_code=502,
            detail=f"供应商履约失败，订单已转入退款处理: {exc}",
        ) from exc

    if db_order.fulfillment_type == RedeemType.MANUAL:
        db_order.status = OrderStatus.PROCESSING
    elif not is_api:
        db_order.status = OrderStatus.COMPLETED
        db_order.completed_at = now
    else:
        try:
            status = _query_api_item_status(session=session, db_order=db_order)
            db_order.status = status
            if status == OrderStatus.COMPLETED:
                db_order.completed_at = now
        except SupplierClientError:
            # 上游订单已创建，查询失败不退款，保持已付款等待手动同步
            db_order.status = OrderStatus.PAID
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order


def sync_order_status(*, session: Session, db_order: Order) -> Order:
    """查询上游订单状态并刷新本地状态快照"""
    if db_order.fulfillment_type != RedeemType.AUTO_API:
        raise HTTPException(status_code=400, detail="订单不包含 API 履约商品")
    if not db_order.supplier_order_id:
        raise HTTPException(
            status_code=400,
            detail=f"商品 {db_order.product_name} 缺少供应商订单号",
        )
    try:
        status = _query_api_item_status(session=session, db_order=db_order)
    except SupplierClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    db_order.status = status
    now = datetime.now(UTC)
    if status == OrderStatus.COMPLETED:
        db_order.completed_at = now
    elif status == OrderStatus.CANCELED:
        db_order.canceled_at = now
    elif status == OrderStatus.REFUNDED:
        db_order.refunded_at = now
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order


def update_order_status(
    *,
    session: Session,
    db_order: Order,
    status: OrderStatus,
) -> Order:
    """管理员手动设置订单状态，仅允许处理中/退单中/已完成/有异常"""
    allowed_statuses = (
        OrderStatus.PROCESSING,
        OrderStatus.REFUNDING,
        OrderStatus.COMPLETED,
        OrderStatus.EXCEPTION,
    )
    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="当前状态不允许手动设置")
    now = datetime.now(UTC)
    db_order.status = status
    if status == OrderStatus.PROCESSING:
        db_order.processing_at = now
    elif status == OrderStatus.COMPLETED:
        db_order.completed_at = now
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order
