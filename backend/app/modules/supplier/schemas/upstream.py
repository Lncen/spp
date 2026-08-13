"""供应商模块：上游数据契约与响应模型

各平台 client 必须把上游返回数据转换为本模块定义的契约类型，
共享业务层只消费这些类型，不接触上游字段名和枚举语义。
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlmodel import Field, SQLModel


class UpstreamBuyParam(SQLModel):
    """上游购买参数（已按平台语义归一化）"""

    key: str
    label: str
    value: str = ""
    description: str = ""
    # 上游原始输入类型，共享业务层再映射为本地 InputType
    input_type: int = 0
    type_config: list[dict[str, Any]] = Field(default_factory=list)
    validate_min: int = 0
    validate_max: int = 0
    default_value: str = ""
    use_default: bool = False


class UpstreamProductSummary(SQLModel):
    """上游商品列表项"""

    upstream_id: str
    name: str = ""
    cost_price: Decimal | None = None


class UpstreamProductDetail(SQLModel):
    """上游商品详情（已按平台语义归一化）"""

    upstream_id: str
    name: str = ""
    cost_price: Decimal
    stock: int = -1
    min_quantity: int = 1
    max_quantity: int = 1_000_000
    purchase_step: int = 1
    is_repeatable: bool = False
    is_batch: bool = True
    is_card_code: bool = False
    is_closed: bool = False
    can_refund: bool = False
    unit: str = "1"
    description: str = ""
    image_urls: list[str] = Field(default_factory=list)
    buy_params: list[UpstreamBuyParam] = Field(default_factory=list)


class UpstreamCategory(SQLModel):
    """上游商品分类"""

    id: str
    name: str
    parent_id: str | None = None


class UpstreamOrder(SQLModel):
    """上游订单（已按平台语义归一化）"""

    upstream_id: str
    status: int = 0
    goods_id: int = 0
    amount: Decimal = Decimal("0")
    selling_price: Decimal = Decimal("0")
    refund_amount: Decimal = Decimal("0")
    buy_number: int = 0
    current_num: int = 0
    start_num: int = 0
    user_id: int = 0
    create_time: int = 0
    update_time: int = 0
    remark: str = ""
    buy_params: list[dict[str, Any]] = Field(default_factory=list)
    card_code_ids: list[int] = Field(default_factory=list)
    status_changes: list[dict[str, Any]] = Field(default_factory=list)


class UpstreamProductPublic(SQLModel):
    """上游商品列表项（与本地货源匹配状态）"""

    upstream_id: str = Field(title="上游商品 ID", description="上游商品 ID")
    name: str = Field(title="商品名称", description="上游商品名称")
    cost_price: Decimal | None = Field(
        default=None,
        title="成本价",
        description="上游价格；列表接口可能不返回",
    )
    synced: bool = Field(
        default=False,
        title="是否已同步",
        description="是否已存在匹配的本地商品货源",
    )
    local_product_id: uuid.UUID | None = Field(
        default=None,
        title="本地商品 ID",
        description="已同步时对应的本地商品 UUID",
    )


class UpstreamCategoryPublic(SQLModel):
    """上游商品分类选项"""

    id: str = Field(title="分类 ID", description="上游商品分类 ID")
    name: str = Field(title="分类名称", description="上游商品分类名称")
    parent_id: str | None = Field(
        default=None,
        title="父分类 ID",
        description="父分类 ID，0 或空表示顶级分类",
    )


class UpstreamCategoriesPublic(SQLModel):
    """上游商品分类列表响应"""

    data: list[UpstreamCategoryPublic]


class UpstreamProductsPublic(SQLModel):
    """上游商品列表响应"""

    data: list[UpstreamProductPublic]
    count: int
