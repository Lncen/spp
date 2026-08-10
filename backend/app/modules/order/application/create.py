"""订单模块：创建订单应用服务"""

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.event_bus import publish as publish_event
from app.modules.order.application.query import to_order_public
from app.modules.order.domain.constants import OrderStatus
from app.modules.order.domain.pricing import calc_unit_price, money
from app.modules.order.domain.validation import _generate_order_no
from app.modules.order.models import Order
from app.modules.order.repositories.order import (
    _load_order_snapshot,
    ensure_no_duplicate_active_order,
    sync_order_params,
)
from app.modules.order.repositories.stock import deduct_stock
from app.modules.order.schemas import (
    AdminOrderPreviewItem,
    AdminOrderResult,
    AdminOrdersCreate,
    AdminOrdersPreviewPublic,
    AdminOrdersPublic,
    OrderCreate,
)
from app.modules.product.product.models import ProductPricing
from app.modules.setting.application.setting_query import get_setting
from app.modules.user.models import User
from app.modules.wallet.service import adjust_balance, get_wallet_by_user_id

logger = logging.getLogger(__name__)


def _publish_order_paid(db_order: Order) -> None:
    """订单创建成功（已付款）后发布事件，失败仅记录日志，不影响下单结果。"""
    try:
        publish_event(
            event_type="order.paid",
            payload={"order_id": str(db_order.id)},
        )
    except Exception:  # noqa: BLE001
        logger.exception("订单 %s 发布 order.paid 事件失败", db_order.order_no)


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


def create_order(*, session: Session, user: User, order_in: OrderCreate) -> Order:
    """创建单张订单：校验用户、钱包、商品与供应商，扣库存并原子扣款

    顺序执行的简单流水线（多步校验与落库），按 AGENTS.md 放宽至 60 行。
    """
    if not user.can_order:
        raise HTTPException(status_code=400, detail="暂无下单权限")
    if not get_setting(session=session, key="order_enabled"):
        raise HTTPException(status_code=403, detail="当前暂停下单，请稍后再试")
    wallet = get_wallet_by_user_id(session=session, user_id=user.id)
    if not wallet:
        raise HTTPException(status_code=400, detail="钱包不存在")
    if not wallet.is_active:
        raise HTTPException(status_code=400, detail="钱包已禁用")

    total, data = build_order_data(
        session=session,
        user=user,
        order_in=order_in,
    )
    ensure_no_duplicate_active_order(
        session=session,
        user_id=user.id,
        product_id=data["product"].id,
        params=data["params"],
    )
    deduct_stock(
        session=session,
        inventory=data["inventory"],
        quantity=data["quantity"],
    )
    if wallet.balance < total:
        raise HTTPException(status_code=400, detail="余额不足")

    db_order = build_order(
        user_id=user.id,
        total=total,
        data=data,
        remark=order_in.remark,
    )
    session.add(db_order)
    session.flush()
    sync_order_params(session=session, db_order=db_order)
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
    session.commit()
    session.refresh(db_order)
    _publish_order_paid(db_order)
    return db_order


def create_orders(
    *,
    session: Session,
    user: User,
    body: AdminOrdersCreate,
) -> AdminOrdersPublic:
    """批量创建用户订单，逐单独立提交，单张失败不影响其他订单

    顺序执行的简单流水线（逐单创建与结果汇总），按 AGENTS.md 放宽至 60 行。
    """
    results: list[AdminOrderResult] = []
    success_count = 0
    failure_count = 0
    for index, order_in in enumerate(body.orders, start=1):
        try:
            db_order = create_order(session=session, user=user, order_in=order_in)
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
            logger.exception("用户下单异常，订单序号 %s", index, exc_info=exc)
            results.append(
                AdminOrderResult(
                    index=index,
                    success=False,
                    detail="订单创建失败，请稍后重试",
                )
            )
        else:
            success_count += 1
            order = to_order_public(session=session, orders=[db_order])[0]
            results.append(AdminOrderResult(index=index, success=True, order=order))
    return AdminOrdersPublic(
        total=len(body.orders),
        success_count=success_count,
        failure_count=failure_count,
        results=results,
    )


def create_admin_order(
    *,
    session: Session,
    operator: User,
    order_in: OrderCreate,
) -> Order:
    """创建管理员订单：跳过钱包与余额校验，仍校验商品、供应商与重复下单

    顺序执行的简单流水线（多步校验与落库），按 AGENTS.md 放宽至 60 行。
    """
    total, data = build_order_data(
        session=session,
        user=operator,
        order_in=order_in,
    )
    ensure_no_duplicate_active_order(
        session=session,
        user_id=operator.id,
        product_id=data["product"].id,
        params=data["params"],
    )
    deduct_stock(
        session=session,
        inventory=data["inventory"],
        quantity=data["quantity"],
    )
    db_order = build_order(
        user_id=operator.id,
        total=total,
        data=data,
        remark=order_in.remark,
    )
    session.add(db_order)
    session.flush()
    sync_order_params(session=session, db_order=db_order)
    session.commit()
    session.refresh(db_order)
    _publish_order_paid(db_order)
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
        total, data = build_order_data(
            session=session,
            user=operator,
            order_in=order_in,
        )
        total_amount += total
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
        total_amount=money(total_amount),
        items=preview_items,
    )


def create_admin_orders(
    *,
    session: Session,
    operator: User,
    body: AdminOrdersCreate,
) -> AdminOrdersPublic:
    """批量创建管理员订单，逐单独立提交，失败原因不泄露供应商信息

    顺序执行的简单流水线（逐单创建与结果汇总），按 AGENTS.md 放宽至 60 行。
    """
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
