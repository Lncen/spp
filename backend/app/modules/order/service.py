"""订单模块：业务逻辑层"""

import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, func, select, update

from app.modules.order.constants import (
    SALABLE_PRODUCT_STATUSES,
    OrderStatus,
)
from app.modules.order.models import Order, OrderItem
from app.modules.order.schemas import OrderCreate
from app.modules.price_template.constants import MONEY_PRECISION
from app.modules.price_template.service import get_user_price
from app.modules.product.constants import RedeemType
from app.modules.product.product.models import (
    Product,
    ProductBuyParam,
    ProductFulfillment,
    ProductInventory,
    ProductPricing,
    ProductSupplier,
)
from app.modules.supplier.models import Supplier
from app.modules.supplier.service.clients.base import (
    SupplierClientBase,
    SupplierClientError,
)
from app.modules.user.models import User
from app.modules.wallet.service import adjust_balance, get_wallet_by_user_id

ACTIVE_ORDER_STATUSES = (
    OrderStatus.CREATED,
    OrderStatus.PROCESSING,
    OrderStatus.COMPLETED,
)


def _generate_order_no() -> str:
    return uuid.uuid4().hex.upper()


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)


def _validate_product_sellable(
    *, product: Product, inventory: ProductInventory, fulfillment: ProductFulfillment
) -> None:
    if not product.is_active:
        raise HTTPException(status_code=400, detail="商品已停用")
    if product.is_closed:
        raise HTTPException(status_code=400, detail="商品已关闭下单")
    if product.status not in SALABLE_PRODUCT_STATUSES:
        raise HTTPException(status_code=400, detail="商品当前不可购买")
    if inventory is None or fulfillment is None:
        raise HTTPException(status_code=400, detail="商品配置不完整")


def _validate_quantity(
    *, inventory: ProductInventory, quantity: int
) -> None:
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
                "购买数量必须是 "
                f"{str(inventory.purchase_step.normalize())} 的整数倍"
            ),
        )


def _validate_and_build_params(
    *,
    params: dict[str, Any] | None,
    buy_params: list[ProductBuyParam],
) -> dict[str, Any]:
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


def _ensure_repeatable(
    *,
    session: Session,
    user_id: uuid.UUID,
    product_id: uuid.UUID,
    is_repeatable: bool,
) -> None:
    if is_repeatable:
        return
    statement = (
        select(OrderItem.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.user_id == user_id,
            OrderItem.product_id == product_id,
            Order.status.in_(ACTIVE_ORDER_STATUSES),
        )
        .limit(1)
    )
    if session.exec(statement).first() is not None:
        raise HTTPException(status_code=400, detail="该商品每人限购一次")


def _calc_unit_price(
    *, session: Session, pricing: ProductPricing, user_level_id: uuid.UUID | None
) -> Decimal:
    base_price = pricing.cost_price + pricing.loss_price
    if pricing.fixed_price is not None:
        unit_price = pricing.fixed_price
    elif pricing.item_coefficient is not None:
        unit_price = base_price * pricing.item_coefficient
    else:
        unit_price = get_user_price(
            session=session,
            base_price=base_price,
            price_template_id=pricing.price_template_id,
            user_level_id=user_level_id,
        )
    return _money(unit_price)


def _deduct_stock(
    *, session: Session, inventory: ProductInventory, quantity: int
) -> None:
    if inventory.stock == -1:
        return
    result = session.exec(
        update(ProductInventory)
        .where(
            ProductInventory.id == inventory.id,
            ProductInventory.stock >= quantity,
        )
        .values(stock=ProductInventory.stock - quantity)
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=400, detail="库存不足")


def _restore_stock(
    *, session: Session, product_id: uuid.UUID | None, quantity: int
) -> None:
    if product_id is None:
        return
    inventory = session.exec(
        select(ProductInventory).where(
            ProductInventory.product_id == product_id
        )
    ).first()
    if inventory is None or inventory.stock == -1:
        return
    inventory.stock += quantity
    session.add(inventory)


def _refund_order(
    *,
    session: Session,
    db_order: Order,
    operator_id: uuid.UUID | None = None,
) -> None:
    wallet = get_wallet_by_user_id(session=session, user_id=db_order.user_id)
    if not wallet:
        raise HTTPException(status_code=400, detail="钱包不存在")
    adjust_balance(
        session=session,
        wallet=wallet,
        amount=db_order.total_amount,
        tx_type="refund",
        ref_type="order",
        ref_id=db_order.id,
        remark=f"订单 {db_order.order_no} 退款",
        operator_id=operator_id,
        commit=False,
    )


def create_order(*, session: Session, user: User, order_in: OrderCreate) -> Order:
    """创建订单：校验商品与钱包，扣库存并原子扣款"""
    if not user.can_order:
        raise HTTPException(status_code=400, detail="暂无下单权限")

    wallet = get_wallet_by_user_id(session=session, user_id=user.id)
    if not wallet:
        raise HTTPException(status_code=400, detail="钱包不存在")
    if not wallet.is_active:
        raise HTTPException(status_code=400, detail="钱包已禁用")

    db_order = Order(
        order_no=_generate_order_no(),
        user_id=user.id,
        remark=order_in.remark,
    )
    session.add(db_order)
    session.flush()

    total = Decimal("0.00")
    prepared_items: list[dict[str, Any]] = []
    for item_in in order_in.items:
        product = session.get(Product, item_in.product_id)
        if not product:
            raise HTTPException(status_code=400, detail="商品不存在")

        inventory = session.exec(
            select(ProductInventory).where(
                ProductInventory.product_id == product.id
            )
        ).first()
        fulfillment = session.exec(
            select(ProductFulfillment).where(
                ProductFulfillment.product_id == product.id
            )
        ).first()
        _validate_product_sellable(
            product=product,
            inventory=inventory,
            fulfillment=fulfillment,
        )
        _validate_quantity(inventory=inventory, quantity=item_in.quantity)
        _ensure_repeatable(
            session=session,
            user_id=user.id,
            product_id=product.id,
            is_repeatable=inventory.is_repeatable,
        )

        buy_params = session.exec(
            select(ProductBuyParam).where(
                ProductBuyParam.product_id == product.id
            )
        ).all()
        params_snapshot = _validate_and_build_params(
            params=item_in.params,
            buy_params=buy_params,
        )
        pricing = session.exec(
            select(ProductPricing).where(
                ProductPricing.product_id == product.id
            )
        ).first()
        if pricing is None:
            raise HTTPException(status_code=400, detail="商品定价配置不存在")

        unit_price = _calc_unit_price(
            session=session,
            pricing=pricing,
            user_level_id=user.level_id,
        )
        subtotal = _money(unit_price * item_in.quantity)
        total += subtotal
        _deduct_stock(session=session, inventory=inventory, quantity=item_in.quantity)
        prepared_items.append(
            {
                "product": product,
                "pricing": pricing,
                "fulfillment": fulfillment,
                "quantity": item_in.quantity,
                "unit_price": unit_price,
                "subtotal": subtotal,
                "params": params_snapshot,
            }
        )

    total = _money(total)
    if wallet.balance < total:
        raise HTTPException(status_code=400, detail="余额不足")
    adjust_balance(
        session=session,
        wallet=wallet,
        amount=-total,
        tx_type="consume",
        ref_type="order",
        ref_id=db_order.id,
        remark=f"订单 {db_order.order_no} 消费",
        operator_id=user.id,
        commit=False,
    )

    for data in prepared_items:
        product = data["product"]
        pricing = data["pricing"]
        session.add(
            OrderItem(
                order_id=db_order.id,
                product_id=product.id,
                product_name=product.name,
                quantity=data["quantity"],
                unit_price=data["unit_price"],
                subtotal=data["subtotal"],
                base_price=pricing.cost_price + pricing.loss_price,
                cost_price=pricing.cost_price,
                loss_price=pricing.loss_price,
                params=data["params"],
                fulfillment_type=data["fulfillment"].fulfillment_type,
                can_refund=data["fulfillment"].can_refund,
            )
        )

    db_order.total_amount = total
    db_order.paid_at = datetime.now(UTC)
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order


def get_order(*, session: Session, order_id: uuid.UUID) -> Order:
    db_order = session.get(Order, order_id)
    if not db_order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return db_order


def get_user_order(
    *, session: Session, order_id: uuid.UUID, user_id: uuid.UUID
) -> Order:
    db_order = get_order(session=session, order_id=order_id)
    if db_order.user_id != user_id:
        raise HTTPException(status_code=404, detail="订单不存在")
    return db_order


def list_orders(
    *,
    session: Session,
    skip: int,
    limit: int,
    status: OrderStatus | None = None,
) -> tuple[list[Order], int]:
    conditions = []
    if status is not None:
        conditions.append(Order.status == status)
    count = session.exec(
        select(func.count()).select_from(Order).where(*conditions)
    ).one()
    statement = (
        select(Order)
        .where(*conditions)
        .order_by(col(Order.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all()), count


def list_user_orders(
    *,
    session: Session,
    user_id: uuid.UUID,
    skip: int,
    limit: int,
) -> tuple[list[Order], int]:
    conditions = [Order.user_id == user_id]
    count = session.exec(
        select(func.count()).select_from(Order).where(*conditions)
    ).one()
    statement = (
        select(Order)
        .where(*conditions)
        .order_by(col(Order.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all()), count


def cancel_order(
    *,
    session: Session,
    db_order: Order,
    operator_id: uuid.UUID | None = None,
) -> Order:
    """取消订单：仅待处理订单可取消，退款并回补库存"""
    if db_order.status != OrderStatus.CREATED:
        raise HTTPException(status_code=400, detail="当前状态不可取消")
    _refund_order(session=session, db_order=db_order, operator_id=operator_id)
    for item in db_order.items:
        _restore_stock(
            session=session,
            product_id=item.product_id,
            quantity=item.quantity,
        )
    db_order.status = OrderStatus.CANCELED
    db_order.canceled_at = datetime.now(UTC)
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order


def _extract_supplier_order_id(result: dict[str, Any]) -> str | None:
    payload = result.get("data") if isinstance(result.get("data"), dict) else result
    for key in ("order_id", "orderId", "id"):
        value = payload.get(key)
        if value is not None:
            return str(value)
    return None


def _fulfill_api_item(*, session: Session, item: OrderItem) -> None:
    supplier_sku = session.exec(
        select(ProductSupplier).where(
            ProductSupplier.product_id == item.product_id
        )
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
            quantity=item.quantity,
            **item.params,
        )
        item.supplier_order_id = _extract_supplier_order_id(result)
        session.add(item)
    finally:
        client.close()


def fulfill_order(
    *,
    session: Session,
    db_order: Order,
    operator_id: uuid.UUID | None = None,
) -> Order:
    """履约订单：自动完成、标记处理中或调用供应商 API"""
    if db_order.status != OrderStatus.CREATED:
        raise HTTPException(status_code=400, detail="当前状态不可履约")

    now = datetime.now(UTC)
    db_order.processing_at = now
    api_items = [
        item for item in db_order.items
        if item.fulfillment_type == RedeemType.AUTO_API
    ]
    manual_items = [
        item for item in db_order.items
        if item.fulfillment_type == RedeemType.MANUAL
    ]

    try:
        for item in api_items:
            _fulfill_api_item(session=session, item=item)
    except SupplierClientError as exc:
        for item in db_order.items:
            _restore_stock(
                session=session,
                product_id=item.product_id,
                quantity=item.quantity,
            )
        _refund_order(
            session=session,
            db_order=db_order,
            operator_id=operator_id,
        )
        db_order.status = OrderStatus.FAILED
        db_order.failed_at = datetime.now(UTC)
        session.add(db_order)
        session.commit()
        session.refresh(db_order)
        raise HTTPException(
            status_code=502,
            detail=f"供应商履约失败，订单已自动退款: {exc}",
        ) from exc

    if manual_items:
        db_order.status = OrderStatus.PROCESSING
    else:
        db_order.status = OrderStatus.COMPLETED
        db_order.completed_at = now
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order


def refund_order(
    *,
    session: Session,
    db_order: Order,
    operator_id: uuid.UUID | None = None,
) -> Order:
    """整单退款：处理中订单回补库存，已完成订单不回补"""
    if db_order.status not in (
        OrderStatus.PROCESSING,
        OrderStatus.COMPLETED,
    ):
        raise HTTPException(status_code=400, detail="当前状态不可退款")
    if any(not item.can_refund for item in db_order.items):
        raise HTTPException(status_code=400, detail="订单包含不支持退款的商品")

    _refund_order(session=session, db_order=db_order, operator_id=operator_id)
    if db_order.status == OrderStatus.PROCESSING:
        for item in db_order.items:
            _restore_stock(
                session=session,
                product_id=item.product_id,
                quantity=item.quantity,
            )
    db_order.status = OrderStatus.REFUNDED
    db_order.refunded_at = datetime.now(UTC)
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order
