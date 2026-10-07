"""商品模块：用户组合数据库模型"""

import uuid

from sqlalchemy import CheckConstraint, Integer
from sqlmodel import Field, SQLModel, UniqueConstraint

from app.core.mixin.models import BaseModelMixin
from app.modules.product.constants import QuantityMode


class ProductCombo(BaseModelMixin, SQLModel, table=True):
    """用户保存的商品组合：一组商品 + 数量，用于一键发起组合下单"""

    __tablename__ = "product_combo"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_product_combo_user_name"),
    )

    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
        index=True,
        title="用户 ID",
        description="组合归属用户的 UUID，删除用户时级联删除组合",
    )
    name: str = Field(
        max_length=50,
        title="组合名称",
        description="同一用户下组合名称唯一",
    )
    remark: str | None = Field(
        default=None,
        max_length=255,
        title="备注",
    )


class ProductComboItem(BaseModelMixin, SQLModel, table=True):
    """组合明细：组合下的单个商品与购买数量"""

    __tablename__ = "product_combo_item"
    __table_args__ = (
        UniqueConstraint(
            "combo_id",
            "product_id",
            name="uq_product_combo_item_combo_product",
        ),
        CheckConstraint(
            "(mode = 1 AND quantity IS NOT NULL) OR "
            "(mode = 2 AND min_quantity IS NOT NULL AND max_quantity IS NOT NULL "
            "AND min_quantity <= max_quantity)",
            name="ck_product_combo_item_quantity_mode",
        ),
    )

    combo_id: uuid.UUID = Field(
        foreign_key="product_combo.id",
        nullable=False,
        ondelete="CASCADE",
        index=True,
        title="组合 ID",
        description="所属组合的 UUID，删除组合时级联删除明细",
    )
    product_id: uuid.UUID = Field(
        foreign_key="product.id",
        nullable=False,
        ondelete="CASCADE",
        index=True,
        title="商品 ID",
        description="组合内商品的 UUID，删除商品时级联删除该明细",
    )
    mode: QuantityMode = Field(
        default=QuantityMode.FIXED,
        sa_type=Integer,
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
    sort: int = Field(
        default=0,
        ge=0,
        title="排序",
        description="组合内展示顺序，取提交时的顺序",
    )
