"""订单模块：API 请求与响应模型"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlmodel import Field, SQLModel

from app.modules.order.domain.constants import OrderStatus
from app.modules.product.constants import RedeemType


class OrderCreate(SQLModel):
    """创建订单请求"""

    product_id: uuid.UUID
    quantity: int = Field(ge=1)
    params: dict[str, Any] | None = Field(
        default=None,
        title="下单参数",
        description="按商品购买参数 key 传值",
    )
    remark: str | None = Field(
        default=None,
        max_length=255,
        title="备注",
    )


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
    fulfill_failed_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    product_id: uuid.UUID | None
    product_name: str
    quantity: int
    start_quantity: int
    current_quantity: int
    unit_price: Decimal
    subtotal: Decimal
    base_price: Decimal
    cost_price: Decimal
    loss_price: Decimal
    params: dict[str, Any]
    fulfillment_type: RedeemType
    supplier_order_id: str | None = None
    supplier_id: uuid.UUID | None = None
    supplier_name: str | None = None
    sku_id: str | None = None
    can_refund: bool
    refunded_amount: Decimal


class OrderListItem(SQLModel):
    """订单列表响应，仅返回列表所需字段"""

    id: uuid.UUID
    username: str | None = Field(
        default=None,
        title="下单用户",
        description="下单用户的用户名，管理员接口返回",
    )
    status: OrderStatus
    total_amount: Decimal
    product_name: str
    quantity: int
    params: dict[str, Any]
    created_at: datetime | None = None


class OrdersPublic(SQLModel):
    """订单列表响应"""

    data: list[OrderListItem]
    count: int


class OrderRefundRequest(SQLModel):
    """管理员手动退款请求"""

    amount: Decimal = Field(
        gt=0,
        max_digits=18,
        decimal_places=7,
        title="退款金额",
        description="退款金额不能超过订单金额",
    )
    remark: str | None = Field(
        default=None,
        max_length=255,
        title="处理备注",
        description="订单售后处理备注，写入订单备注",
    )


class OrderRemarkRequest(SQLModel):
    """管理员订单售后处理请求"""

    remark: str | None = Field(
        default=None,
        max_length=255,
        title="处理备注",
        description="订单售后处理备注，写入订单备注",
    )


class OrderStatusUpdateRequest(SQLModel):
    """管理员设置订单状态请求"""

    status: OrderStatus = Field(title="目标状态")


class SupplierOrderIdUpdateRequest(SQLModel):
    """管理员补录供应商订单号请求"""

    supplier_order_id: str = Field(
        min_length=1,
        max_length=255,
        title="供应商订单号",
        description="人工确认上游已下单后补录",
    )


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
