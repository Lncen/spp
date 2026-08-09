"""订单模块：下单校验与计价辅助函数"""

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.modules.order.constants import (
    ACTIVE_ORDER_STATUSES,
    SALABLE_PRODUCT_STATUSES,
    OrderStatus,
)
from app.modules.order.models import Order
from app.modules.order.schemas import OrderCreate
from app.modules.order.service.pricing import calc_unit_price, money
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


def _generate_order_no() -> str:
    """生成唯一订单号"""
    return uuid.uuid4().hex.upper()


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


def _validate_supplier_available(
    *, session: Session, product: Product
) -> ProductSupplier | None:
    """校验商品供应商可用；自营商品跳过，返回货源记录供订单快照"""
    supplier_sku = session.exec(
        select(ProductSupplier).where(ProductSupplier.product_id == product.id)
    ).first()
    if supplier_sku is None or supplier_sku.supplier_id is None:
        return supplier_sku
    supplier = session.get(Supplier, supplier_sku.supplier_id)
    if supplier is None:
        return supplier_sku
    if supplier.platform == PlatformEnum.SELF:
        return supplier_sku
    if not supplier.is_active or supplier.status != "active":
        raise HTTPException(status_code=400, detail="商品暂不可下单，请稍后重试")
    return supplier_sku


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


def normalize_param_value(value: Any) -> str:
    """参数值统一转字符串比较，复合类型用 JSON 稳定序列化"""
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _normalize_params(params: dict[str, Any] | None) -> dict[str, str]:
    """参数按 key 排序后统一序列化，用于重复下单比较"""
    return {
        str(key): normalize_param_value(value)
        for key, value in sorted((params or {}).items())
    }


def ensure_no_duplicate_active_order(
    *,
    session: Session,
    user_id: uuid.UUID,
    product_id: uuid.UUID,
    params: dict[str, Any],
) -> None:
    """同用户同商品同参数且未完成的订单禁止重复创建，数量不参与比较"""
    normalized = _normalize_params(params)
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


def _load_order_snapshot(
    *,
    session: Session,
    order_in: OrderCreate,
) -> dict[str, Any]:
    """校验商品、供应商、数量与参数，返回不含价格的订单快照字段"""
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
    supplier_sku = _validate_supplier_available(session=session, product=product)
    _validate_quantity(inventory=inventory, quantity=order_in.quantity)

    buy_params = session.exec(
        select(ProductBuyParam).where(ProductBuyParam.product_id == product.id)
    ).all()
    params_snapshot = _validate_and_build_params(
        params=order_in.params,
        buy_params=buy_params,
    )
    return {
        "product": product,
        "inventory": inventory,
        "fulfillment": fulfillment,
        "supplier_id": supplier_sku.supplier_id if supplier_sku else None,
        "sku_id": supplier_sku.sku_id if supplier_sku else None,
        "quantity": order_in.quantity,
        "params": params_snapshot,
    }


def build_order_data(
    *,
    session: Session,
    user: User,
    order_in: OrderCreate,
) -> tuple[Decimal, dict[str, Any]]:
    """校验单张订单并计算总额，返回 (总额, 快照数据)"""
    data = _load_order_snapshot(session=session, order_in=order_in)
    pricing = session.exec(
        select(ProductPricing).where(
            ProductPricing.product_id == data["product"].id
        )
    ).first()
    if pricing is None:
        raise HTTPException(status_code=400, detail="商品定价配置不存在")

    unit_price = calc_unit_price(
        session=session,
        pricing=pricing,
        user_level_id=user.level_id,
    )
    subtotal = money(unit_price * order_in.quantity)
    data.update(
        {
            "pricing": pricing,
            "unit_price": unit_price,
            "subtotal": subtotal,
        }
    )
    return money(subtotal), data


def build_order(
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
        start_quantity=data["quantity"],
        current_quantity=data["quantity"],
        unit_price=data["unit_price"],
        subtotal=data["subtotal"],
        base_price=pricing.cost_price + pricing.loss_price,
        cost_price=pricing.cost_price,
        loss_price=pricing.loss_price,
        params=data["params"],
        fulfillment_type=data["fulfillment"].fulfillment_type,
        can_refund=data["fulfillment"].can_refund,
        supplier_id=data["supplier_id"],
        sku_id=data["sku_id"],
        paid_at=datetime.now(UTC),
    )
