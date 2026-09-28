"""订单模块：创建订单应用服务"""

import logging
import uuid
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.event_bus import create_event_in_session, dispatch_event
from app.core.time import get_datetime_cn
from app.modules.automation.models import AutomationEvent
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
from app.modules.wallet.application.wallet_adjust import adjust_balance
from app.modules.wallet.application.wallet_query import get_or_create_user_wallet
from app.modules.wallet.models import Wallet

logger = logging.getLogger(__name__)


def _queue_order_paid_event(*, session: Session, db_order: Order) -> AutomationEvent:
    """在订单事务内登记 order.paid 事件，随订单一起提交，避免事件丢失"""
    return create_event_in_session(
        session=session,
        event_type="order.paid",
        payload={"order_id": str(db_order.id)},
    )


def _dispatch_order_paid_event(event: AutomationEvent) -> None:
    """订单提交后分发 order.paid；失败仅记录日志，事件已在库中可追溯补发"""
    try:
        dispatch_event(event)
    except Exception:  # noqa: BLE001
        logger.exception("order.paid 事件分发失败 event_id=%s", event.id)


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
        supplier_name=data["supplier_name"],
        sku_id=data["sku_id"],
        paid_at=get_datetime_cn(),
    )


def _create_order_core(
    *,
    session: Session,
    user: User,
    order_in: OrderCreate,
    wallet: Wallet | None,
    require_wallet: bool = False,
) -> Order:
    """公共下单流水线：普通下单与管理员代下共享，避免两套校验逐渐不一致

    两者都执行：order_enabled、商品/价格、库存、防重复、构造订单落库、
    order.paid 事件；require_wallet 时校验钱包存在与启用，
    wallet 非 None 时额外做余额校验与扣款。
    下单权限（order:create / order:admin_create）由 API 层权限依赖校验，
    本层不再判断用户字段。
    顺序执行的简单流水线（多步校验与落库），按 AGENTS.md 放宽至 60 行。
    """
    if not get_setting(session=session, key="order_enabled"):
        raise HTTPException(status_code=403, detail="当前暂停下单，请稍后再试")
    if require_wallet:
        if wallet is None:
            raise HTTPException(status_code=400, detail="钱包不存在")
        if not wallet.is_active:
            raise HTTPException(status_code=400, detail="钱包已禁用")

    # 校验单张订单并计算总额
    total, data = build_order_data(
        session=session,
        user=user,
        order_in=order_in,
    )

    # 校验无重复下单（在库存行锁内执行，并发下可看到已提交订单）
    ensure_no_duplicate_active_order(
        session=session,
        user_id=user.id,
        product_id=data["product"].id,
        params=data["params"],
    )

    # 校验余额（仅钱包下单）
    if wallet is not None and wallet.balance < total:
        raise HTTPException(status_code=400, detail="余额不足")

    # 扣库存：先锁库存行，串行化同一商品的下单事务
    deduct_stock(
        session=session,
        inventory=data["inventory"],
        quantity=data["quantity"],
    )


    # 构造订单模型
    db_order = build_order(
        user_id=user.id,
        total=total,
        data=data,
        remark=order_in.remark,
    )
    # 提交订单
    session.add(db_order)
    session.flush()
    # 展开订单参数写入 order_params
    sync_order_params(session=session, db_order=db_order)
    # 事件随订单事务落库，提交后统一分发
    event = _queue_order_paid_event(session=session, db_order=db_order)
    # 扣款（仅钱包下单）
    if wallet is not None:
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
    # 提交事务
    session.commit()
    # 刷新订单数据
    session.refresh(db_order)
    _dispatch_order_paid_event(event)
    return db_order


def _create_orders_batch(
    *,
    session: Session,
    user: User,
    body: AdminOrdersCreate,
    wallet: Wallet | None,
    require_wallet: bool = False,
) -> AdminOrdersPublic:
    """批量下单公共循环：逐单独立提交，单张失败不影响其他订单"""
    results: list[AdminOrderResult] = []
    success_count = 0
    failure_count = 0
    for index, order_in in enumerate(body.orders, start=1):
        try:
            db_order = _create_order_core(
                session=session,
                user=user,
                order_in=order_in,
                wallet=wallet,
                require_wallet=require_wallet,
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
            logger.exception("下单异常，订单序号 %s", index, exc_info=exc)
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


def create_orders(
    *,
    session: Session,
    user: User,
    body: AdminOrdersCreate,
) -> AdminOrdersPublic:
    """批量创建用户订单：逐单校验钱包并扣款，逐单独立返回创建状态"""
    wallet = get_or_create_user_wallet(session=session, user_id=user.id)
    return _create_orders_batch(
        session=session,
        user=user,
        body=body,
        wallet=wallet,
        require_wallet=True,
    )


def create_admin_orders(
    *,
    session: Session,
    operator: User,
    body: AdminOrdersCreate,
) -> AdminOrdersPublic:
    """批量创建管理员订单：跳过钱包校验与扣款，
    其余校验（下单权限、下单开关、商品、库存、防重复）与普通下单一致
    """
    return _create_orders_batch(
        session=session,
        user=operator,
        body=body,
        wallet=None,
    )


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
