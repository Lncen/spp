"""商品模块：商品数据库模型"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, CheckConstraint, Index, Integer, Text, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.core.mixin.models import BaseModelMixin
from app.modules.product.category.models import ProductCategory
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


class Product(BaseModelMixin, SQLModel, table=True):
    """商品数据库模型"""

    __tablename__ = "product"

    name: str = Field(
        max_length=255,
        title="商品名称",
        description="商品名称",
    )
    category_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="product_category.id",
        nullable=True,
        ondelete="SET NULL",
        index=True,
        title="本地分类 ID",
        description="本地分类的 UUID，删除分类后置空",
    )
    source_type: SourceType = Field(
        default=SourceType.LOCAL,
        sa_type=Integer,
        index=True,
        title="商品来源",
        description="决定商品是否可编辑及库存逻辑",
    )
    status: ProductStatus = Field(
        default=ProductStatus.PENDING_REVIEW,
        sa_type=Integer,
        index=True,
        title="商品状态",
        description="商品当前状态",
    )
    is_closed: bool = Field(
        default=False,
        index=True,
        title="是否关闭下单",
        description="关闭后商品不可下单",
    )
    sort: int = Field(
        default=0,
        ge=0,
        index=True,
        title="排序权重",
        description="排序权重（本地），数值越大越靠前",
    )
    type: ProductType = Field(
        default=ProductType.NORMAL_PRODUCT,
        sa_type=Integer,
        title="商品类型",
        description="商品类型，影响下单与履约行为",
    )

    category: ProductCategory = Relationship(back_populates="products")
    product_supplier: ProductSupplier = Relationship(
        back_populates="product",
        sa_relationship_kwargs={"uselist": False},
    )
    pricing: ProductPricing = Relationship(
        back_populates="product",
        sa_relationship_kwargs={"uselist": False},
    )
    inventory: ProductInventory = Relationship(
        back_populates="product",
        sa_relationship_kwargs={"uselist": False},
    )
    fulfillment: ProductFulfillment = Relationship(
        back_populates="product",
        sa_relationship_kwargs={"uselist": False},
    )
    buy_params: list[ProductBuyParam] = Relationship(back_populates="product")

    __table_args__ = (
        Index("ix_product_status_sort", "status", "sort"),
        Index("ix_product_category_status", "category_id", "status"),
    )


class ProductSupplier(BaseModelMixin, SQLModel, table=True):
    """商品货源数据库模型"""

    __tablename__ = "product_supplier"

    product_id: uuid.UUID = Field(
        foreign_key="product.id",
        unique=True,
        nullable=False,
        ondelete="CASCADE",
        title="商品 ID",
        description="所属商品的 UUID，一个商品最多一条货源记录",
    )
    supplier_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="supplier.id",
        nullable=True,
        ondelete="SET NULL",
        index=True,
        title="供应商 ID",
        description="关联供应商的 UUID，供应商删除后置空",
    )
    sku_id: str | None = Field(
        default=None,
        max_length=255,
        index=True,
        title="供应商 SKU",
        description="供应商侧的商品 SKU 标识",
    )

    product: Product = Relationship(back_populates="product_supplier")


class ProductPricing(BaseModelMixin, SQLModel, table=True):
    """商品价格配置数据库模型"""

    __tablename__ = "product_pricing"

    product_id: uuid.UUID = Field(
        foreign_key="product.id",
        unique=True,
        nullable=False,
        ondelete="CASCADE",
        title="商品 ID",
        description="所属商品的 UUID，一个商品只有一条价格配置",
    )
    price_template_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="price_template.id",
        nullable=True,
        ondelete="RESTRICT",
        index=True,
        title="价格模板 ID",
        description="关联价格模板的 UUID；与固定价格、商品系数互斥",
    )
    cost_price: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        max_digits=18,
        decimal_places=8,
        title="成本价",
        description="商品成本价",
    )
    loss_price: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0"),
        max_digits=18,
        decimal_places=8,
        title="固定损耗",
        description="实际成本 = 成本价 + 损耗",
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
        default=8,
        ge=0,
        le=32767,
        title="价格展示精度",
        description="前端显示价格时保留的小数位数",
    )

    product: Product = Relationship(back_populates="pricing")

    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN price_template_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN fixed_price IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN item_coefficient IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_product_pricing_price_rule",
        ),
    )

    @property
    def rule_type(self) -> RuleType:
        """当前定价规则，由字段状态派生。"""
        if self.fixed_price is not None:
            return RuleType.FIXED_PRICE
        if self.item_coefficient is not None:
            return RuleType.PERCENTAGE_PRICE
        return RuleType.CATEGORY_PRICE

    @property
    def config_mode(self) -> str:
        """当前配置模式标识，供外部快速判断。"""
        if self.fixed_price is not None:
            return "fixed_price"
        if self.item_coefficient is not None:
            return "item_coefficient"
        return "category"


class ProductInventory(BaseModelMixin, SQLModel, table=True):
    """商品库存与购买限制数据库模型"""

    __tablename__ = "product_inventory"

    product_id: uuid.UUID = Field(
        foreign_key="product.id",
        unique=True,
        nullable=False,
        ondelete="CASCADE",
        title="商品 ID",
        description="所属商品的 UUID，一个商品只有一条库存配置",
    )
    min_quantity: int = Field(
        default=1,
        ge=1,
        title="最小购买数量",
        description="单次购买的最小数量",
    )
    max_quantity: int = Field(
        default=1_000_000,
        ge=1,
        title="最大购买数量",
        description="单次购买的最大数量",
    )
    is_repeatable: bool = Field(
        default=False,
        title="是否允许重复购买",
        description="同一用户是否可以重复购买该商品",
    )
    is_batch: bool = Field(
        default=True,
        title="是否支持批量购买",
        description="是否允许单次购买多个商品",
    )
    purchase_step: Decimal = Field(
        default=Decimal("1"),
        gt=Decimal("0"),
        max_digits=10,
        decimal_places=4,
        title="购买步长",
        description="购买数量必须是步长的整数倍，例如 100、200、300",
    )
    stock: int = Field(
        default=-1,
        title="库存数量",
        description="-1 表示无限库存",
    )

    product: Product = Relationship(back_populates="inventory")

    __table_args__ = (
        CheckConstraint(
            "stock >= -1",
            name="ck_product_inventory_stock_gte_minus_one",
        ),
        CheckConstraint(
            "min_quantity <= max_quantity",
            name="ck_product_inventory_min_lte_max",
        ),
    )


class ProductFulfillment(BaseModelMixin, SQLModel, table=True):
    """商品履约与售后数据库模型"""

    __tablename__ = "product_fulfillment"

    product_id: uuid.UUID = Field(
        foreign_key="product.id",
        unique=True,
        nullable=False,
        ondelete="CASCADE",
        title="商品 ID",
        description="所属商品的 UUID，一个商品只有一条履约配置",
    )
    fulfillment_type: RedeemType = Field(
        default=RedeemType.AUTOMATIC,
        sa_type=Integer,
        title="发货方式",
        description="商品发货/履约方式",
    )
    can_refund: bool = Field(
        default=False,
        title="是否允许退款",
        description="该商品是否支持退款",
    )
    after_sale_rules: str = Field(
        default="",
        sa_type=Text,
        title="售后规则说明",
        description="商品售后规则文本",
    )
    description: str = Field(
        default="",
        sa_type=Text,
        title="商品描述",
        description="商品详情描述",
    )
    unit: str = Field(
        default="1",
        max_length=32,
        title="数量单位",
        description="商品数量单位，如 1、件、份",
    )
    input_fields_overridden: bool = Field(
        default=False,
        title="参数是否被本地修改",
        description="购买参数模板是否被本地覆盖",
    )
    params_template: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_type=JSON,
        title="购买参数模板",
        description="原始 JSON，预期格式为 [{'key': ..., 'label': ..., ...}]",
    )

    product: Product = Relationship(back_populates="fulfillment")


class ProductBuyParam(BaseModelMixin, SQLModel, table=True):
    """商品下单参数数据库模型"""

    __tablename__ = "product_buy_param"

    product_id: uuid.UUID = Field(
        foreign_key="product.id",
        nullable=False,
        ondelete="CASCADE",
        title="所属商品 ID",
        description="所属商品的 UUID，删除商品时级联删除",
    )
    key: str = Field(
        max_length=128,
        title="参数 Key",
        description="参数键，同一商品内唯一",
    )
    label: str = Field(
        max_length=128,
        title="参数名称",
        description="展示给用户看的参数名称",
    )
    value: str = Field(
        default="",
        max_length=128,
        title="参数值",
        description="当前填写的参数值",
    )
    description: str = Field(
        default="",
        sa_type=Text,
        title="参数描述/提示",
        description="参数填写说明",
    )
    input_type: InputType = Field(
        default=InputType.TEXT,
        sa_type=Integer,
        title="输入类型",
        description="前端渲染该参数时使用的输入控件类型",
    )
    type_config: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_type=JSON,
        title="类型扩展配置",
        description="输入类型的扩展配置，如选择项列表",
    )
    default_value: str = Field(
        default="",
        sa_type=Text,
        title="默认值",
        description="参数默认值",
    )
    use_default: bool = Field(
        default=False,
        title="是否使用默认值",
        description="下单时是否直接使用默认值",
    )
    is_required: bool = Field(
        default=True,
        title="是否必填",
        description="下单时该参数是否必填",
    )
    is_hidden: bool = Field(
        default=False,
        title="是否隐藏",
        description="下单表单中是否隐藏该参数",
    )
    is_edit: bool = Field(
        default=False,
        title="是否可以修改",
        description="用户下单时是否可以修改该参数",
    )
    validate_min: int = Field(
        default=1,
        ge=0,
        title="最小长度/值",
        description="0 表示不限制",
    )
    validate_max: int = Field(
        default=100,
        ge=0,
        title="最大长度/值",
        description="0 表示不限制",
    )

    product: Product = Relationship(back_populates="buy_params")

    __table_args__ = (
        UniqueConstraint("product_id", "key", name="uq_product_buy_param_product_key"),
    )
