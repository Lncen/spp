"""订单模块：API 请求与响应模型"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlmodel import Field, SQLModel

from app.modules.order.constants import OrderStatus
from app.modules.product.constants import RedeemType


class OrderItemCreate(SQLModel):
    """下单商品项请求"""

    product_id: uuid.UUID
    quantity: int = Field(ge=1)
    params: dict[str, Any] | None = Field(
        default=None,
        title="下单参数",
        description="按商品购买参数 key 传值",
    )


class OrderCreate(SQLModel):
    """创建订单请求"""

    items: list[OrderItemCreate] = Field(
        min_length=1,
        max_length=50,
        title="商品项",
    )
    remark: str | None = Field(
        default=None,
        max_length=255,
        title="备注",
    )


class OrderItemPublic(SQLModel):
    """订单商品项响应"""

    id: uuid.UUID
    product_id: uuid.UUID | None
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    base_price: Decimal
    cost_price: Decimal
    loss_price: Decimal
    params: dict[str, Any]
    fulfillment_type: RedeemType
    supplier_order_id: str | None = None
    can_refund: bool


class OrderPublic(SQLModel):
    """订单响应"""

    id: uuid.UUID
    order_no: str
    user_id: uuid.UUID
    username: str | None = Field(
        default=None,
        title="下单用户",
        description="下单用户的用户名，管理员接口返回",
    )
    status: OrderStatus
    total_amount: Decimal
    currency: str
    remark: str | None = None
    paid_at: datetime | None = None
    processing_at: datetime | None = None
    completed_at: datetime | None = None
    canceled_at: datetime | None = None
    refunded_at: datetime | None = None
    failed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    items: list[OrderItemPublic] = Field(default_factory=list)


class OrdersPublic(SQLModel):
    """订单列表响应"""

    data: list[OrderPublic]
    count: int


class AdminOrdersCreate(SQLModel):
    """管理员批量下单请求"""

    orders: list[OrderCreate] = Field(
        min_length=1,
        max_length=100,
        title="订单列表",
        description="每张订单独立创建，单张失败不影响其他订单",
    )


class AdminOrderResult(SQLModel):
    """管理员下单单张订单结果"""

    index: int = Field(title="原始顺序索引", description="从 1 开始")
    success: bool
    order: OrderPublic | None = None
    detail: str | None = None


class AdminOrdersPublic(SQLModel):
    """管理员批量下单响应"""

    total: int
    success_count: int
    failure_count: int
    results: list[AdminOrderResult]


class AdminOrderPreviewItem(SQLModel):
    """管理员下单结算预览商品行"""

    index: int = Field(title="原始顺序索引", description="从 1 开始")
    product_id: uuid.UUID
    product_name: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


class AdminOrdersPreviewPublic(SQLModel):
    """管理员下单结算预览响应"""

    total: int
    total_amount: Decimal
    items: list[AdminOrderPreviewItem] = Field(default_factory=list)
