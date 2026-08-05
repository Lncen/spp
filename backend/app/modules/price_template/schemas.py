"""价格模板模块：API 请求与响应模型"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import field_validator
from sqlmodel import Field, SQLModel

from app.modules.price_template.constants import (
    DEFAULT_DISCOUNT_RATE,
    LEVEL_MAX,
    LEVEL_MIN,
)


class PriceTemplateRuleIn(SQLModel):
    """设置单个等级折扣请求"""

    level: int = Field(
        ge=LEVEL_MIN,
        le=LEVEL_MAX,
        title="用户等级",
        description="用户等级编号 1-10",
    )
    discount_rate: Decimal = Field(
        default=DEFAULT_DISCOUNT_RATE,
        ge=Decimal("0"),
        le=Decimal("10.0000"),
        max_digits=5,
        decimal_places=4,
        title="折扣率",
        description="实际价格 = 商品基准价 × 折扣率；15 折为 1.5000",
    )


def _validate_rules(rules: list[PriceTemplateRuleIn]) -> list[PriceTemplateRuleIn]:
    """校验等级折扣列表不允许重复等级"""
    levels = [rule.level for rule in rules]
    if len(levels) != len(set(levels)):
        raise ValueError("等级不能重复")
    return rules


class PriceTemplateBase(SQLModel):
    """价格模板基础属性"""

    name: str = Field(
        min_length=1,
        max_length=255,
        title="模板名称",
        description="价格模板名称，全局唯一",
    )
    is_default: bool = Field(default=False, title="是否默认")
    description: str | None = Field(
        default=None,
        max_length=255,
        title="模板描述",
    )
    is_default: bool = Field(
        default=False,
        title="是否默认模板",
        description="创建商品未选择模板时默认使用的模板，仅允许一个为 True",
    )


class PriceTemplateCreate(PriceTemplateBase):
    """创建价格模板请求；未传的等级自动按 15 折补齐"""

    rules: list[PriceTemplateRuleIn] = Field(
        default_factory=list,
        title="等级折扣列表",
        description="1-10 等级折扣，未设置等级的折扣按 15 折（1.5000）",
    )

    @field_validator("rules")
    @classmethod
    def validate_rules(
        cls, rules: list[PriceTemplateRuleIn]
    ) -> list[PriceTemplateRuleIn]:
        return _validate_rules(rules)


class PriceTemplateUpdate(SQLModel):
    """更新价格模板请求（全部可选）；rules 只覆盖传入等级，其余等级保留"""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        title="模板名称",
    )
    description: str | None = Field(
        default=None,
        max_length=255,
        title="模板描述",
    )
    is_active: bool | None = Field(default=None, title="是否启用")
    is_default: bool | None = Field(default=None, title="是否默认模板")
    rules: list[PriceTemplateRuleIn] | None = Field(
        default=None,
        title="等级折扣列表",
        description="传入的等级折扣将被覆盖，未传入等级保留原折扣",
    )

    @field_validator("rules")
    @classmethod
    def validate_rules(
        cls, rules: list[PriceTemplateRuleIn] | None
    ) -> list[PriceTemplateRuleIn] | None:
        if rules is None:
            return None
        return _validate_rules(rules)


class PriceTemplateRulePublic(SQLModel):
    """价格模板等级折扣响应"""

    id: uuid.UUID
    level: int
    discount_rate: Decimal


class PriceTemplatePublic(SQLModel):
    """价格模板公开响应"""

    id: uuid.UUID
    name: str
    description: str | None
    is_default: bool
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None
    rules: list[PriceTemplateRulePublic]


class PriceTemplatesPublic(SQLModel):
    """价格模板列表响应"""

    data: list[PriceTemplatePublic]
    count: int
