"""订单模块：业务逻辑层"""

import json
import logging
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
from app.modules.order.schemas import (
    AdminOrderPreviewItem,
    AdminOrderResult,
    AdminOrdersCreate,
    AdminOrdersPreviewPublic,
    AdminOrdersPublic,
    OrderCreate,
    OrderPublic,
)
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

logger = logging.getLogger(__name__)

# 未完成订单状态：存在时禁止同商品同参数重复下单
ACTIVE_ORDER_STATUSES = (
    OrderStatus.PAID,
    OrderStatus.PENDING,
    OrderStatus.PROCESSING,
    OrderStatus.SUPPLEMENTING,
    OrderStatus.REFUNDING,
    OrderStatus.COMPLETED,
    OrderStatus.EXCEPTION,
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


def _validate_quantity(*, inventory: ProductInventory, quantity: int) -> None:
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


def _validate_supplier_available(*, session: Session, product: Product) -> None:
    """校验商品供应商可用，失败原因不向客户端暴露供应商信息"""
    supplier_sku = session.exec(
        select(ProductSupplier).where(ProductSupplier.product_id == product.id)
    ).first()
    supplier = (
        session.get(Supplier, supplier_sku.supplier_id)
        if supplier_sku is not None and supplier_sku.supplier_id is not None
        else None
    )
    if supplier is None or not supplier.is_active or supplier.status != "active":
        raise HTTPException(status_code=400, detail="商品暂不可下单，请稍后重试")


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


def _normalize_param_value(value: Any) -> str:
    """参数值统一转字符串比较，复合类型用 JSON 稳定序列化"""
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _normalize_params(params: dict[str, Any] | None) -> dict[str, str]:
    return {
        str(key): _normalize_param_value(value)
        for key, value in sorted((params or {}).items())
    }


def _ensure_no_duplicate_active_order(
    *,
    session: Session,
    user_id: uuid.UUID,
    product_id: uuid.UUID,
    params: dict[str, Any],
    seen_items: set[tuple[str, tuple[tuple[str, str], ...]]],
) -> None:
    """同用户同商品同参数且未完成的订单禁止重复创建，数量不参与比较"""
    normalized = _normalize_params(params)
    key = (str(product_id), tuple(normalized.items()))
    if key in seen_items:
        raise HTTPException(
            status_code=400,
            detail="该商品相同参数订单未完成，禁止重复下单",
        )
    statement = (
        select(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.user_id == user_id,
            OrderItem.product_id == product_id,
            Order.status.in_(ACTIVE_ORDER_STATUSES),
        )
    )
    for item in session.exec(statement).all():
        if _normalize_params(item.params) == normalized:
            raise HTTPException(
                status_code=400,
                detail="该商品相同参数订单未完成，禁止重复下单",
            )
    seen_items.add(key)


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
        select(ProductInventory).where(ProductInventory.product_id == product_id)
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
        status=OrderStatus.PAID,
    )
    session.add(db_order)
    session.flush()

    total = Decimal("0.00")
    prepared_items: list[dict[str, Any]] = []
    seen_items: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    for item_in in order_in.items:
        product = session.get(Product, item_in.product_id)
        if not product:
            raise HTTPException(status_code=400, detail="商品不存在")

        inventory = session.exec(
            select(ProductInventory).where(ProductInventory.product_id == product.id)
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

        buy_params = session.exec(
            select(ProductBuyParam).where(ProductBuyParam.product_id == product.id)
        ).all()
        params_snapshot = _validate_and_build_params(
            params=item_in.params,
            buy_params=buy_params,
        )
        _ensure_no_duplicate_active_order(
            session=session,
            user_id=user.id,
            product_id=product.id,
            params=params_snapshot,
            seen_items=seen_items,
        )
        pricing = session.exec(
            select(ProductPricing).where(ProductPricing.product_id == product.id)
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


def _build_admin_order_items(
    *,
    session: Session,
    operator: User,
    order_in: OrderCreate,
) -> tuple[Decimal, list[dict[str, Any]]]:
    """校验管理员订单商品项并计价，不扣库存不落库"""
    total = Decimal("0.00")
    prepared_items: list[dict[str, Any]] = []
    for item_in in order_in.items:
        product = session.get(Product, item_in.product_id)
        if not product:
            raise HTTPException(status_code=400, detail="商品不存在")

        inventory = session.exec(
            select(ProductInventory).where(ProductInventory.product_id == product.id)
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
        _validate_supplier_available(session=session, product=product)
        _validate_quantity(inventory=inventory, quantity=item_in.quantity)

        buy_params = session.exec(
            select(ProductBuyParam).where(ProductBuyParam.product_id == product.id)
        ).all()
        params_snapshot = _validate_and_build_params(
            params=item_in.params,
            buy_params=buy_params,
        )
        pricing = session.exec(
            select(ProductPricing).where(ProductPricing.product_id == product.id)
        ).first()
        if pricing is None:
            raise HTTPException(status_code=400, detail="商品定价配置不存在")

        unit_price = _calc_unit_price(
            session=session,
            pricing=pricing,
            user_level_id=operator.level_id,
        )
        subtotal = _money(unit_price * item_in.quantity)
        total += subtotal
        prepared_items.append(
            {
                "product": product,
                "inventory": inventory,
                "pricing": pricing,
                "fulfillment": fulfillment,
                "quantity": item_in.quantity,
                "unit_price": unit_price,
                "subtotal": subtotal,
                "params": params_snapshot,
            }
        )
    return _money(total), prepared_items


def create_admin_order(
    *,
    session: Session,
    operator: User,
    order_in: OrderCreate,
) -> Order:
    """创建管理员订单：跳过钱包与余额校验，仍校验商品、供应商状态与重复下单"""
    total, prepared_items = _build_admin_order_items(
        session=session,
        operator=operator,
        order_in=order_in,
    )
    seen_items: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
    for data in prepared_items:
        _ensure_no_duplicate_active_order(
            session=session,
            user_id=operator.id,
            product_id=data["product"].id,
            params=data["params"],
            seen_items=seen_items,
        )
    db_order = Order(
        order_no=_generate_order_no(),
        user_id=operator.id,
        remark=order_in.remark,
        status=OrderStatus.PAID,
    )
    session.add(db_order)
    session.flush()

    for data in prepared_items:
        _deduct_stock(
            session=session,
            inventory=data["inventory"],
            quantity=data["quantity"],
        )
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


def preview_admin_orders(
    *,
    session: Session,
    operator: User,
    body: AdminOrdersCreate,
) -> AdminOrdersPreviewPublic:
    """批量结算预览：复用下单校验与计价，不扣库存不落库"""
    preview_items: list[AdminOrderPreviewItem] = []
    total_amount = Decimal("0.00")
    for index, order_in in enumerate(body.orders, start=1):
        total, prepared_items = _build_admin_order_items(
            session=session,
            operator=operator,
            order_in=order_in,
        )
        total_amount += total
        for data in prepared_items:
            preview_items.append(
                AdminOrderPreviewItem(
                    index=index,
                    product_id=data["product"].id,
                    product_name=data["product"].name,
                    quantity=data["quantity"],
                    unit_price=data["unit_price"],
                    subtotal=data["subtotal"],
                )
            )
    return AdminOrdersPreviewPublic(
        total=len(body.orders),
        total_amount=_money(total_amount),
        items=preview_items,
    )


def create_admin_orders(
    *,
    session: Session,
    operator: User,
    body: AdminOrdersCreate,
) -> AdminOrdersPublic:
    """批量创建管理员订单，逐单独立提交，失败原因不泄露供应商信息"""
    results: list[AdminOrderResult] = []
    success_count = 0
    failure_count = 0
    for index, order_in in enumerate(body.orders, start=1):
        try:
            db_order = create_admin_order(
                session=session,
                operator=operator,
                order_in=order_in,
            )
        except HTTPException as exc:
            failure_count += 1
            session.rollback()
            detail = exc.detail if isinstance(exc.detail, str) else None
            results.append(
                AdminOrderResult(
                    index=index,
                    success=False,
                    detail=detail or "订单创建失败，请稍后重试",
                )
            )
        except Exception as exc:  # noqa: BLE001
            failure_count += 1
            session.rollback()
            logger.exception("管理员下单异常，订单序号 %s", index, exc_info=exc)
            results.append(
                AdminOrderResult(
                    index=index,
                    success=False,
                    detail="订单创建失败，请稍后重试",
                )
            )
        else:
            success_count += 1
            results.append(
                AdminOrderResult(
                    index=index,
                    success=True,
                    order=to_order_public(session=session, orders=[db_order])[0],
                )
            )
    return AdminOrdersPublic(
        total=len(body.orders),
        success_count=success_count,
        failure_count=failure_count,
        results=results,
    )


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
    user_id: uuid.UUID | None = None,
) -> tuple[list[Order], int]:
    conditions = []
    if status is not None:
        conditions.append(Order.status == status)
    if user_id is not None:
        conditions.append(Order.user_id == user_id)
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


def to_order_public(*, session: Session, orders: list[Order]) -> list[OrderPublic]:
    """将订单模型转换为响应模型，并附加下单用户 username"""
    if not orders:
        return []
    user_ids = {order.user_id for order in orders}
    users = session.exec(select(User).where(User.id.in_(user_ids))).all()
    username_by_id = {user.id: user.username for user in users}
    result: list[OrderPublic] = []
    for order in orders:
        data = OrderPublic.model_validate(order).model_dump()
        data["username"] = username_by_id.get(order.user_id)
        result.append(OrderPublic.model_validate(data))
    return result


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
    """取消订单：已付款/待处理/处理中可取消，退款并回补库存"""
    if db_order.status not in (
        OrderStatus.PAID,
        OrderStatus.PENDING,
        OrderStatus.PROCESSING,
    ):
        raise HTTPException(status_code=400, detail="当前状态不可取消")
    _refund_order(session=session, db_order=db_order, operator_id=operator_id)
    for item in db_order.items:
        _restore_stock(
            session=session,
            product_id=item.product_id,
            quantity=item.quantity,
        )
    now = datetime.now(UTC)
    db_order.status = OrderStatus.REFUNDED
    db_order.canceled_at = now
    db_order.refunded_at = now
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
        select(ProductSupplier).where(ProductSupplier.product_id == item.product_id)
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


def _query_api_item_status(*, session: Session, item: OrderItem) -> OrderStatus:
    supplier_sku = session.exec(
        select(ProductSupplier).where(ProductSupplier.product_id == item.product_id)
    ).first()
    if supplier_sku is None or supplier_sku.supplier_id is None:
        raise SupplierClientError("商品未配置供应商")
    supplier = session.get(Supplier, supplier_sku.supplier_id)
    if not supplier:
        raise SupplierClientError("供应商不存在")
    client = SupplierClientBase.get_client(supplier)
    try:
        result = client.query_order([int(item.supplier_order_id)])
    finally:
        client.close()
    raw_status = _extract_upstream_status(result)
    if raw_status is None:
        raise SupplierClientError(f"上游订单 {item.supplier_order_id} 缺少状态字段")
    try:
        return OrderStatus(raw_status)
    except ValueError as exc:
        raise SupplierClientError(
            f"上游订单 {item.supplier_order_id} 返回未知状态 {raw_status}"
        ) from exc


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
    api_items = [
        item for item in db_order.items if item.fulfillment_type == RedeemType.AUTO_API
    ]
    manual_items = [
        item for item in db_order.items if item.fulfillment_type == RedeemType.MANUAL
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
        db_order.status = OrderStatus.REFUNDED
        db_order.failed_at = now
        db_order.refunded_at = now
        session.add(db_order)
        session.commit()
        session.refresh(db_order)
        raise HTTPException(
            status_code=502,
            detail=f"供应商履约失败，订单已自动退款: {exc}",
        ) from exc

    upstream_statuses: list[OrderStatus] = []
    for item in api_items:
        try:
            upstream_statuses.append(_query_api_item_status(session=session, item=item))
        except SupplierClientError:
            # 上游订单已创建，查询失败不退款，保持已付款等待手动同步
            upstream_statuses = []
            break

    if manual_items:
        db_order.status = OrderStatus.PROCESSING
    elif not api_items:
        db_order.status = OrderStatus.COMPLETED
        db_order.completed_at = now
    elif upstream_statuses:
        db_order.status = _merge_upstream_statuses(upstream_statuses)
        if db_order.status == OrderStatus.COMPLETED:
            db_order.completed_at = now
    else:
        db_order.status = OrderStatus.PAID
    session.add(db_order)
    session.commit()
    session.refresh(db_order)
    return db_order


def sync_order_status(*, session: Session, db_order: Order) -> Order:
    """查询上游订单状态并刷新本地状态快照"""
    api_items = [
        item for item in db_order.items if item.fulfillment_type == RedeemType.AUTO_API
    ]
    if not api_items:
        raise HTTPException(status_code=400, detail="订单不包含 API 履约商品")
    statuses: list[OrderStatus] = []
    for item in api_items:
        if not item.supplier_order_id:
            raise HTTPException(
                status_code=400,
                detail=f"商品 {item.product_name} 缺少供应商订单号",
            )
        try:
            statuses.append(_query_api_item_status(session=session, item=item))
        except SupplierClientError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    db_order.status = _merge_upstream_statuses(statuses)
    now = datetime.now(UTC)
    if db_order.status == OrderStatus.COMPLETED:
        db_order.completed_at = now
    elif db_order.status == OrderStatus.CANCELED:
        db_order.canceled_at = now
    elif db_order.status == OrderStatus.REFUNDED:
        db_order.refunded_at = now
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
