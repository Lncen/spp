"""价格模板模块：数据库模型"""

import uuid
from decimal import Decimal

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.core.mixin.models import BaseModelMixin
from app.modules.price_template.constants import DEFAULT_DISCOUNT_RATE
from app.modules.price_template.schemas import PriceTemplateBase


class PriceTemplate(BaseModelMixin, PriceTemplateBase, table=True):
    """价格模板数据库模型"""

    __tablename__ = "price_template"

    rules: list[PriceTemplateRule] = Relationship(
        back_populates="price_template",
        cascade_delete=True,
    )


class PriceTemplateRule(BaseModelMixin, SQLModel, table=True):
    """价格模板等级折扣规则数据库模型"""

    __tablename__ = "price_template_rule"

    price_template_id: uuid.UUID = Field(
        foreign_key="price_template.id",
        nullable=False,
        ondelete="CASCADE",
        title="价格模板 ID",
        description="所属价格模板的 UUID，删除模板时级联删除",
    )
    level_id: uuid.UUID = Field(
        foreign_key="user_level.id",
        nullable=False,
        ondelete="CASCADE",
        title="用户等级 ID",
        description="关联的用户等级 UUID",
    )
    discount_rate: Decimal = Field(
        default=DEFAULT_DISCOUNT_RATE,
        ge=Decimal("0"),
        le=Decimal("10.0000"),
        max_digits=5,
        decimal_places=4,
        title="折扣率",
        description="该等级实际价格 = 商品基准价 × 折扣率；15 折为 1.5000",
    )

    price_template: PriceTemplate = Relationship(back_populates="rules")

    __table_args__ = (UniqueConstraint("price_template_id", "level_id"),)
