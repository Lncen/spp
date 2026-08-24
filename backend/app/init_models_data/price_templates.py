"""价格模板初始数据"""

import uuid

from sqlmodel import Session, select

from app.core.time import get_datetime_cn
from app.init_models_data.levels import LEVEL_UUIDS
from app.modules.price_template.constants import DEFAULT_DISCOUNT_RATE
from app.modules.price_template.models import PriceTemplate, PriceTemplateRule

# 默认价格模板的固定 UUID（确保幂等性）
DEFAULT_PRICE_TEMPLATE_UUID = uuid.UUID("b0000000-0000-0000-0000-000000000001")


def seed_price_templates(*, session: Session) -> None:
    """播种默认价格模板及其 1-10 等级折扣规则，幂等安全（已有默认模板则跳过）"""
    existing = session.exec(
        select(PriceTemplate).where(PriceTemplate.is_default)
    ).first()
    if existing:
        return

    now = get_datetime_cn()
    session.add(
        PriceTemplate(
            id=DEFAULT_PRICE_TEMPLATE_UUID,
            name="默认模板",
            description="创建商品未选择模板时自动使用的默认价格模板",
            is_default=True,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
    for level_id in LEVEL_UUIDS.values():
        session.add(
            PriceTemplateRule(
                price_template_id=DEFAULT_PRICE_TEMPLATE_UUID,
                level_id=level_id,
                discount_rate=DEFAULT_DISCOUNT_RATE,
                created_at=now,
                updated_at=now,
            )
        )
    session.commit()
