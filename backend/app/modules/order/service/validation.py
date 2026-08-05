"""订单模块：下单校验与计价辅助函数"""

import json
import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select, update

from app.modules.order.constants import (
    SALABLE_PRODUCT_STATUSES,
    OrderStatus,
)
from app.modules.order.models import Order
from app.modules.order.schemas import OrderCreate
from app.modules.price_template.constants import MONEY_PRECISION
from app.modules.price_template.service import get_user_price
from app.modules.product.product.models import (
    Product,
    ProductBuyParam,
    ProductFulfillment,
    ProductInventory,
    ProductPricing,
    ProductSupplier,
)
from app.modules.supplier.models import Supplier
from app.modules.supplier.schemas import PlatformEnum
from app.modules.user.models import User

# 未完成订单状态：存在时禁止同商品同参数重复下单
ACTIVE_ORDER_STATUSES = (
    OrderStatus.PAID,
    OrderStatus.PENDING,
    OrderStatus.PROCESSING,
    OrderStatus.SUPPLEMENTING,
    OrderStatus.REFUNDING,
    OrderStatus.COMPLETED,
    OrderStatus.EXCEPTION,
    OrderStatus.APPLYING_AFTER_SALE,
)


def _generate_order_no() -> str:
    """生成唯一订单号"""
    return uuid.uuid4().hex.upper()


def _money(value: Decimal) -> Decimal:
    """金额按业务精度四舍五入"""
    return value.quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)


def _validate_product_sellable(
    *, product: Product, inventory: ProductInventory, fulfillment: ProductFulfillment
) -> None:
    """校验商品可售状态与配置完整性"""
    if not product.is_active:
        raise HTTPException(status_code=400, detail="商品已停用")
    if product.is_closed:
        raise HTTPException(status_code=400, detail="商品已关闭下单")
    if product.status not in SALABLE_PRODUCT_STATUSES:
        raise HTTPException(status_code=400, detail="商品当前不可购买")
    if inventory is None or fulfillment is None:
        raise HTTPException(status_code=400, detail="商品配置不完整")


def _validate_quantity(*, inventory: ProductInventory, quantity: int) -> None:
    """校验购买数量满足商品库存限制"""
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
    """校验商品供应商可用；自营商品跳过，失败原因不向客户端暴露供应商信息"""
    supplier_sku = session.exec(
        select(ProductSupplier).where(ProductSupplier.product_id == product.id)
    ).first()
    if supplier_sku is None or supplier_sku.supplier_id is None:
        return
    supplier = session.get(Supplier, supplier_sku.supplier_id)
    if supplier is None:
        return
    if supplier.platform == PlatformEnum.SELF:
        return
    if not supplier.is_active or supplier.status != "active":
        raise HTTPException(status_code=400, detail="商品暂不可下单，请稍后重试")


def _validate_and_build_params(
    *,
    params: dict[str, Any] | None,
    buy_params: list[ProductBuyParam],
) -> dict[str, Any]:
    """按商品购买参数定义补齐并校验下单参数"""
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
    """参数按 key 排序后统一序列化，用于重复下单比较"""
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
    statement = select(Order).where(
        Order.user_id == user_id,
        Order.product_id == product_id,
        Order.status.in_(ACTIVE_ORDER_STATUSES),
    )
    for order in session.exec(statement).all():
        if _normalize_params(order.params) == normalized:
            raise HTTPException(
                status_code=400,
                detail="该商品相同参数订单未完成，禁止重复下单",
            )
    seen_items.add(key)


def _calc_unit_price(
    *, session: Session, pricing: ProductPricing, user_level_id: uuid.UUID | None
) -> Decimal:
    """按定价规则计算成交单价"""
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
    """条件扣减库存，库存不足时抛错；无限库存直接跳过"""
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
    """订单取消或退款时回补库存"""
    if product_id is None:
        return
    inventory = session.exec(
        select(ProductInventory).where(ProductInventory.product_id == product_id)
    ).first()
    if inventory is None or inventory.stock == -1:
        return
    inventory.stock += quantity
    session.add(inventory)


def _build_order_data(
    *,
    session: Session,
    user: User,
    order_in: OrderCreate,
) -> tuple[Decimal, dict[str, Any]]:
    """校验单张订单商品、供应商、数量与参数，返回总额和快照数据"""
    product = session.get(Product, order_in.product_id)
    if not product:
        raise HTTPException(status_code=400, detail="商品不存在")

    inventory = session.exec(
        select(ProductInventory).where(ProductInventory.product_id == product.id)
    ).first()
    fulfillment = session.exec(
        select(ProductFulfillment).where(ProductFulfillment.product_id == product.id)
    ).first()
    _validate_product_sellable(
        product=product,
        inventory=inventory,
        fulfillment=fulfillment,
    )
    _validate_supplier_available(session=session, product=product)
    _validate_quantity(inventory=inventory, quantity=order_in.quantity)

    buy_params = session.exec(
        select(ProductBuyParam).where(ProductBuyParam.product_id == product.id)
    ).all()
    params_snapshot = _validate_and_build_params(
        params=order_in.params,
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
        user_level_id=user.level_id,
    )
    subtotal = _money(unit_price * order_in.quantity)
    data = {
        "product": product,
        "inventory": inventory,
        "pricing": pricing,
        "fulfillment": fulfillment,
        "quantity": order_in.quantity,
        "unit_price": unit_price,
        "subtotal": subtotal,
        "params": params_snapshot,
    }
    return _money(subtotal), data


def _build_order(
    *,
    user_id: uuid.UUID,
    total: Decimal,
    data: dict[str, Any],
    remark: str | None,
) -> Order:
    """按商品快照构造订单模型，不提交"""
    product = data["product"]
    pricing = data["pricing"]
    return Order(
        order_no=_generate_order_no(),
        user_id=user_id,
        remark=remark,
        status=OrderStatus.PAID,
        total_amount=total,
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
        paid_at=datetime.now(UTC),
    )
