"""订单模块：数据库模型"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Integer
from sqlmodel import Field, Relationship, SQLModel

from app.core.mixin.models import BaseModelMixin
from app.modules.order.constants import OrderStatus
from app.modules.product.constants import RedeemType


class Order(BaseModelMixin, SQLModel, table=True):
    """订单数据库模型"""

    __tablename__ = "orders"

    order_no: str = Field(
        max_length=64,
        unique=True,
        index=True,
        title="订单号",
        description="系统生成的唯一订单号",
    )
    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
        index=True,
        title="用户 ID",
        description="下单用户的 UUID",
    )
    status: OrderStatus = Field(
        default=OrderStatus.PAID,
        sa_type=Integer,
        index=True,
        title="订单状态",
    )
    total_amount: Decimal = Field(
        default=Decimal("0.00"),
        max_digits=18,
        decimal_places=2,
        title="订单金额",
        description="订单实付金额，下单时从钱包扣除",
    )
    currency: str = Field(
        default="CNY",
        max_length=3,
        title="币种",
    )
    remark: str | None = Field(
        default=None,
        max_length=255,
        title="备注",
    )
    paid_at: datetime | None = Field(
        default=None,
        title="支付时间",
        description="下单即支付，支付成功后写入",
    )
    processing_at: datetime | None = Field(
        default=None,
        title="开始处理时间",
    )
    completed_at: datetime | None = Field(
        default=None,
        title="完成时间",
    )
    canceled_at: datetime | None = Field(
        default=None,
        title="取消时间",
    )
    refunded_at: datetime | None = Field(
        default=None,
        title="退款时间",
    )
    failed_at: datetime | None = Field(
        default=None,
        title="失败时间",
    )

    items: list[OrderItem] = Relationship(
        back_populates="order",
        cascade_delete=True,
    )


class OrderItem(BaseModelMixin, SQLModel, table=True):
    """订单商品项数据库模型"""

    __tablename__ = "order_items"

    order_id: uuid.UUID = Field(
        foreign_key="orders.id",
        nullable=False,
        ondelete="CASCADE",
        index=True,
        title="订单 ID",
    )
    product_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="product.id",
        nullable=True,
        ondelete="SET NULL",
        index=True,
        title="商品 ID",
        description="商品删除后置空，商品名与价格保留快照",
    )
    product_name: str = Field(
        max_length=255,
        title="商品名称快照",
    )
    quantity: int = Field(
        ge=1,
        title="购买数量",
    )
    unit_price: Decimal = Field(
        max_digits=18,
        decimal_places=2,
        title="成交单价",
    )
    subtotal: Decimal = Field(
        max_digits=18,
        decimal_places=2,
        title="小计金额",
    )
    base_price: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=8,
        title="基准价快照",
        description="成本价 + 固定损耗",
    )
    cost_price: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=8,
        title="成本价快照",
    )
    loss_price: Decimal = Field(
        default=Decimal("0"),
        max_digits=18,
        decimal_places=8,
        title="固定损耗快照",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        title="下单参数快照",
    )
    fulfillment_type: RedeemType = Field(
        default=RedeemType.AUTOMATIC,
        sa_type=Integer,
        title="履约方式快照",
    )
    supplier_order_id: str | None = Field(
        default=None,
        max_length=255,
        index=True,
        title="供应商订单号",
    )
    can_refund: bool = Field(
        default=False,
        title="是否允许退款",
        description="下单时的商品退款规则快照",
    )

    order: Order = Relationship(back_populates="items")
