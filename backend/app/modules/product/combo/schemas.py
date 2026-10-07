"""商品模块：用户组合 API 请求与响应模型"""

import uuid
from datetime import datetime
from typing import Self

from pydantic import model_validator
from sqlmodel import Field, SQLModel

from app.modules.product.constants import ProductStatus, QuantityMode


class ProductComboItemCreate(SQLModel):
    """组合明细请求"""

    product_id: uuid.UUID = Field(
        title="商品 ID",
        description="组合内商品的 UUID",
    )
    mode: QuantityMode = Field(
        default=QuantityMode.FIXED,
        title="数量模式",
        description="1=固定数量（用 quantity），2=随机数量（用 min_quantity / max_quantity）",
    )
    quantity: int | None = Field(
        default=None,
        ge=1,
        title="固定数量",
        description="固定数量模式下的购买数量",
    )
    min_quantity: int | None = Field(
        default=None,
        ge=1,
        title="最小数量",
        description="随机数量模式下的最小购买数量",
    )
    max_quantity: int | None = Field(
        default=None,
        ge=1,
        title="最大数量",
        description="随机数量模式下的最大购买数量",
    )

    @model_validator(mode="after")
    def validate_quantity_mode(self) -> Self:
        if self.mode == QuantityMode.FIXED:
            if self.quantity is None:
                raise ValueError("固定数量模式必须提供 quantity")
            if self.min_quantity is not None or self.max_quantity is not None:
                raise ValueError("固定数量模式不应提供 min_quantity / max_quantity")
            return self
        if self.min_quantity is None or self.max_quantity is None:
            raise ValueError("随机数量模式必须提供 min_quantity 与 max_quantity")
        if self.min_quantity > self.max_quantity:
            raise ValueError("最小数量不能大于最大数量")
        if self.quantity is not None:
            raise ValueError("随机数量模式不应提供 quantity")
        return self


class ProductComboCreate(SQLModel):
    """创建组合请求"""

    name: str = Field(
        min_length=1,
        max_length=50,
        title="组合名称",
        description="同一用户下组合名称唯一",
    )
    remark: str | None = Field(
        default=None,
        max_length=255,
        title="备注",
    )
    items: list[ProductComboItemCreate] = Field(
        min_length=1,
        max_length=100,
        title="组合明细",
        description="组合内商品与数量，下单时按此批量提交",
    )


class ProductComboUpdate(SQLModel):
    """更新组合请求（全部可选，items 传入则整体替换）"""

    name: str | None = Field(
        default=None, min_length=1, max_length=50, title="组合名称"
    )
    remark: str | None = Field(default=None, max_length=255, title="备注")
    items: list[ProductComboItemCreate] | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        title="组合明细",
    )


class ProductComboItemPublic(SQLModel):
    """组合明细响应，仅暴露用户可见的商品展示字段"""

    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    image_url: str | None = None
    mode: QuantityMode
    quantity: int | None = None
    min_quantity: int | None = None
    max_quantity: int | None = None
    sort: int
    status: ProductStatus
    is_closed: bool


class ProductComboPublic(SQLModel):
    """组合详情响应"""

    id: uuid.UUID
    name: str
    remark: str | None = None
    item_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    items: list[ProductComboItemPublic] = Field(default_factory=list)


class ProductComboListItem(SQLModel):
    """组合列表响应，仅返回列表所需字段"""

    id: uuid.UUID
    name: str
    remark: str | None = None
    item_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductCombosPublic(SQLModel):
    """组合列表响应"""

    data: list[ProductComboListItem]
    count: int
