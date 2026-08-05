"""商品模块：商品 API 请求与响应模型"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Self

from pydantic import field_validator, model_validator
from sqlmodel import Field, SQLModel

from app.modules.product.constants import (
    COEFF_MAX,
    COEFF_MIN,
    InputType,
    ProductStatus,
    ProductType,
    RedeemType,
    RuleType,
    SourceType,
)


class ProductSupplierCreate(SQLModel):
    """商品货源创建请求"""

    supplier_id: uuid.UUID | None = Field(
        default=None,
        title="供应商 ID",
        description="为空表示未关联供应商",
    )
    sku_id: str | None = Field(
        default=None,
        max_length=255,
        title="供应商 SKU",
        description="供应商侧的商品 SKU 标识",
    )


class ProductSupplierUpdate(SQLModel):
    """商品货源更新请求（全部可选）"""

    supplier_id: uuid.UUID | None = Field(default=None, title="供应商 ID")
    sku_id: str | None = Field(default=None, max_length=255, title="供应商 SKU")


class ProductPricingCreate(SQLModel):
    """商品价格配置创建请求"""

    price_template_id: uuid.UUID | None = Field(
        default=None,
        title="价格模板 ID",
        description="关联价格模板的 UUID，与固定价格、商品系数互斥",
    )
    cost_price: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        max_digits=18,
        decimal_places=8,
        title="成本价",
    )
    loss_price: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        max_digits=18,
        decimal_places=8,
        title="固定损耗",
    )
    fixed_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=18,
        decimal_places=8,
        title="固定价格",
        description="设置后直接作为最终售价，与价格模板、商品独立系数互斥",
    )
    item_coefficient: Decimal | None = Field(
        default=None,
        ge=COEFF_MIN,
        le=COEFF_MAX,
        max_digits=6,
        decimal_places=4,
        title="商品独立系数",
        description="替代模板加价率，与价格模板、固定价格互斥",
    )
    price_display_precision: int = Field(
        default=6,
        ge=0,
        le=32767,
        title="价格展示精度",
        description="前端显示价格时保留的小数位数",
    )

    @model_validator(mode="after")
    def validate_price_rule(self) -> Self:
        filled_count = sum(
            1
            for value in (
                self.price_template_id,
                self.fixed_price,
                self.item_coefficient,
            )
            if value is not None
        )
        if filled_count != 1:
            raise ValueError("固定价格、商品系数、价格模板三者必须且只能设置一个")
        return self


class ProductPricingUpdate(SQLModel):
    """商品价格配置更新请求（全部可选）"""

    price_template_id: uuid.UUID | None = Field(
        default=None,
        title="价格模板 ID",
        description="显式传 null 表示清除价格模板",
    )
    cost_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=18,
        decimal_places=8,
        title="成本价",
    )
    loss_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=18,
        decimal_places=8,
        title="固定损耗",
    )
    fixed_price: Decimal | None = Field(
        default=None,
        ge=Decimal("0"),
        max_digits=18,
        decimal_places=8,
        title="固定价格",
        description="显式传 null 表示清除固定价格",
    )
    item_coefficient: Decimal | None = Field(
        default=None,
        ge=COEFF_MIN,
        le=COEFF_MAX,
        max_digits=6,
        decimal_places=4,
        title="商品独立系数",
        description="显式传 null 表示清除商品独立系数",
    )
    price_display_precision: int | None = Field(
        default=None,
        ge=0,
        le=32767,
        title="价格展示精度",
    )


class ProductInventoryCreate(SQLModel):
    """商品库存配置创建请求"""

    min_quantity: int = Field(default=1, ge=1, title="最小购买数量")
    max_quantity: int = Field(default=1_000_000, ge=1, title="最大购买数量")
    is_repeatable: bool = Field(default=False, title="是否允许重复购买")
    is_batch: bool = Field(default=True, title="是否支持批量购买")
    purchase_step: Decimal = Field(
        default=Decimal("1"),
        gt=Decimal("0"),
        max_digits=10,
        decimal_places=4,
        title="购买步长",
    )
    stock: int = Field(
        default=-1,
        ge=-1,
        title="库存数量",
        description="-1 表示无限库存",
    )

    @field_validator("purchase_step")
    @classmethod
    def validate_purchase_step_integer(cls, value: Decimal) -> Decimal:
        if value != value.to_integral_value():
            raise ValueError("购买步长必须是整数")
        return value

    @model_validator(mode="after")
    def validate_quantity_bounds(self) -> Self:
        if self.min_quantity > self.max_quantity:
            raise ValueError("最小购买数量不能大于最大购买数量")
        return self


class ProductInventoryUpdate(SQLModel):
    """商品库存配置更新请求（全部可选）"""

    min_quantity: int | None = Field(default=None, ge=1, title="最小购买数量")
    max_quantity: int | None = Field(default=None, ge=1, title="最大购买数量")
    is_repeatable: bool | None = Field(default=None, title="是否允许重复购买")
    is_batch: bool | None = Field(default=None, title="是否支持批量购买")
    purchase_step: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
        max_digits=10,
        decimal_places=4,
        title="购买步长",
    )
    stock: int | None = Field(default=None, ge=-1, title="库存数量")

    @field_validator("purchase_step")
    @classmethod
    def validate_purchase_step_integer(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and value != value.to_integral_value():
            raise ValueError("购买步长必须是整数")
        return value

    @model_validator(mode="after")
    def validate_quantity_bounds(self) -> Self:
        if (
            self.min_quantity is not None
            and self.max_quantity is not None
            and self.min_quantity > self.max_quantity
        ):
            raise ValueError("最小购买数量不能大于最大购买数量")
        return self


class ProductFulfillmentCreate(SQLModel):
    """商品履约配置创建请求"""

    fulfillment_type: RedeemType = Field(
        default=RedeemType.AUTOMATIC,
        title="发货方式",
    )
    can_refund: bool = Field(default=False, title="是否允许退款")
    after_sale_rules: str = Field(default="", title="售后规则说明")
    description: str = Field(default="", title="商品描述")
    unit: str = Field(default="1", max_length=32, title="数量单位")
    input_fields_overridden: bool = Field(
        default=False,
        title="参数是否被本地修改",
    )
    params_template: list[dict[str, Any]] = Field(
        default_factory=list,
        title="购买参数模板",
    )


class ProductFulfillmentUpdate(SQLModel):
    """商品履约配置更新请求（全部可选）"""

    fulfillment_type: RedeemType | None = Field(default=None, title="发货方式")
    can_refund: bool | None = Field(default=None, title="是否允许退款")
    after_sale_rules: str | None = Field(default=None, title="售后规则说明")
    description: str | None = Field(default=None, title="商品描述")
    unit: str | None = Field(default=None, max_length=32, title="数量单位")
    input_fields_overridden: bool | None = Field(
        default=None,
        title="参数是否被本地修改",
    )
    params_template: list[dict[str, Any]] | None = Field(
        default=None,
        title="购买参数模板",
    )


class ProductBuyParamCreate(SQLModel):
    """商品下单参数创建请求"""

    key: str = Field(
        min_length=1,
        max_length=128,
        title="参数 Key",
        description="参数键，同一商品内唯一",
    )
    label: str = Field(
        min_length=1,
        max_length=128,
        title="参数名称",
    )
    value: str = Field(default="", max_length=128, title="参数值")
    description: str = Field(default="", title="参数描述/提示")
    input_type: InputType = Field(default=InputType.TEXT, title="输入类型")
    type_config: list[dict[str, Any]] = Field(
        default_factory=list,
        title="类型扩展配置",
    )
    default_value: str = Field(default="", title="默认值")
    use_default: bool = Field(default=False, title="是否使用默认值")
    is_required: bool = Field(default=True, title="是否必填")
    is_hidden: bool = Field(default=False, title="是否隐藏")
    is_edit: bool = Field(default=False, title="是否可以修改")
    validate_min: int = Field(default=1, ge=0, title="最小长度/值")
    validate_max: int = Field(default=100, ge=0, title="最大长度/值")


class ProductBuyParamUpdate(SQLModel):
    """商品下单参数更新请求（全部可选）"""

    key: str | None = Field(default=None, min_length=1, max_length=128, title="参数 Key")
    label: str | None = Field(default=None, min_length=1, max_length=128, title="参数名称")
    value: str | None = Field(default=None, max_length=128, title="参数值")
    description: str | None = Field(default=None, title="参数描述/提示")
    input_type: InputType | None = Field(default=None, title="输入类型")
    type_config: list[dict[str, Any]] | None = Field(default=None, title="类型扩展配置")
    default_value: str | None = Field(default=None, title="默认值")
    use_default: bool | None = Field(default=None, title="是否使用默认值")
    is_required: bool | None = Field(default=None, title="是否必填")
    is_hidden: bool | None = Field(default=None, title="是否隐藏")
    is_edit: bool | None = Field(default=None, title="是否可以修改")
    validate_min: int | None = Field(default=None, ge=0, title="最小长度/值")
    validate_max: int | None = Field(default=None, ge=0, title="最大长度/值")


class ProductCreate(SQLModel):
    """创建商品请求"""

    name: str = Field(min_length=1, max_length=255, title="商品名称")
    category_id: uuid.UUID = Field(title="本地分类 ID")
    image_id: uuid.UUID | None = Field(default=None, title="商品主图 ID")
    source_type: SourceType = Field(
        default=SourceType.LOCAL,
        title="商品来源",
    )
    status: ProductStatus = Field(
        default=ProductStatus.PENDING_REVIEW,
        title="商品状态",
    )
    is_closed: bool = Field(default=False, title="是否关闭下单")
    sort: int = Field(default=0, ge=0, title="排序权重")
    type: ProductType = Field(
        default=ProductType.NORMAL_PRODUCT,
        title="商品类型",
    )
    supplier: ProductSupplierCreate | None = Field(default=None, title="商品货源")
    pricing: ProductPricingCreate
    inventory: ProductInventoryCreate = Field(
        default_factory=ProductInventoryCreate,
        title="库存配置",
    )
    fulfillment: ProductFulfillmentCreate = Field(
        default_factory=ProductFulfillmentCreate,
        title="履约配置",
    )
    buy_params: list[ProductBuyParamCreate] = Field(
        default_factory=list,
        title="下单参数列表",
    )


class ProductUpdate(SQLModel):
    """更新商品请求（全部可选）"""

    name: str | None = Field(default=None, min_length=1, max_length=255, title="商品名称")
    category_id: uuid.UUID | None = Field(default=None, title="本地分类 ID")
    image_id: uuid.UUID | None = Field(
        default=None,
        title="商品主图 ID",
        description="显式传 null 表示清除商品主图",
    )
    source_type: SourceType | None = Field(default=None, title="商品来源")
    status: ProductStatus | None = Field(default=None, title="商品状态")
    is_closed: bool | None = Field(default=None, title="是否关闭下单")
    sort: int | None = Field(default=None, ge=0, title="排序权重")
    type: ProductType | None = Field(default=None, title="商品类型")
    is_active: bool | None = Field(default=None, title="是否启用")
    supplier: ProductSupplierUpdate | None = Field(
        default=None,
        title="商品货源",
        description="传 null 表示清除货源记录",
    )
    pricing: ProductPricingUpdate | None = Field(
        default=None,
        title="价格配置",
        description="传 null 将被拒绝，商品必须保留价格配置",
    )
    inventory: ProductInventoryUpdate | None = Field(
        default=None,
        title="库存配置",
        description="传 null 将被拒绝，商品必须保留库存配置",
    )
    fulfillment: ProductFulfillmentUpdate | None = Field(
        default=None,
        title="履约配置",
        description="传 null 将被拒绝，商品必须保留履约配置",
    )
    buy_params: list[ProductBuyParamUpdate] | None = Field(
        default=None,
        title="下单参数列表",
        description="传 null 表示清空下单参数，传列表表示整体替换",
    )


class ProductSupplierPublic(SQLModel):
    """商品货源公开响应"""

    supplier_id: uuid.UUID | None
    supplier_name: str | None = None
    sku_id: str | None = None


class ProductPricingPublic(SQLModel):
    """商品价格配置公开响应"""

    price_template_id: uuid.UUID | None
    cost_price: Decimal
    loss_price: Decimal
    fixed_price: Decimal | None
    item_coefficient: Decimal | None
    price_display_precision: int
    rule_type: RuleType
    config_mode: str


class ProductInventoryPublic(SQLModel):
    """商品库存配置公开响应"""

    min_quantity: int
    max_quantity: int
    is_repeatable: bool
    is_batch: bool
    purchase_step: Decimal
    stock: int


class ProductFulfillmentPublic(SQLModel):
    """商品履约配置公开响应"""

    fulfillment_type: RedeemType
    can_refund: bool
    after_sale_rules: str
    description: str
    unit: str
    input_fields_overridden: bool
    params_template: list[dict[str, Any]]


class ProductBuyParamPublic(SQLModel):
    """商品下单参数公开响应"""

    id: uuid.UUID
    key: str
    label: str
    value: str
    description: str
    input_type: InputType
    type_config: list[dict[str, Any]]
    default_value: str
    use_default: bool
    is_required: bool
    is_hidden: bool
    is_edit: bool
    validate_min: int
    validate_max: int


class ProductPublic(SQLModel):
    """商品公开响应"""

    id: uuid.UUID
    name: str
    category_id: uuid.UUID | None
    category_name: str | None = None
    image_id: uuid.UUID | None = None
    image_url: str | None = None
    source_type: SourceType
    status: ProductStatus
    is_closed: bool
    sort: int
    type: ProductType
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    supplier: ProductSupplierPublic | None = None
    pricing: ProductPricingPublic | None = None
    inventory: ProductInventoryPublic | None = None
    fulfillment: ProductFulfillmentPublic | None = None
    buy_params: list[ProductBuyParamPublic] = Field(default_factory=list)


class ProductsPublic(SQLModel):
    """商品列表响应"""

    data: list[ProductPublic]
    count: int
