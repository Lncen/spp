"""商品模块：创建商品应用服务"""

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.price_template.service import get_default_price_template
from app.modules.product.category.service import sync_category_product_count
from app.modules.product.product.domain.validation import validate_buy_param_keys
from app.modules.product.product.models import Product
from app.modules.product.product.repositories.product import (
    create_product as create_product_repo,
)
from app.modules.product.product.repositories.product import (
    validate_product_refs,
)
from app.modules.product.product.schemas import ProductCreate


def create_product(*, session: Session, product_in: ProductCreate) -> Product:
    """创建商品及其关联配置"""
    price_template_id = product_in.pricing.price_template_id
    if (
        price_template_id is None
        and product_in.pricing.fixed_price is None
        and product_in.pricing.item_coefficient is None
    ):
        default_template = get_default_price_template(session=session)
        if default_template is None:
            raise HTTPException(status_code=400, detail="默认价格模板不存在或未启用")
        price_template_id = default_template.id

    validate_product_refs(
        session=session,
        category_id=product_in.category_id,
        price_template_id=price_template_id,
        supplier_id=(product_in.supplier.supplier_id if product_in.supplier else None),
        image_id=product_in.image_id,
    )
    validate_buy_param_keys(params=product_in.buy_params)

    db_product = create_product_repo(
        session=session,
        product_in=product_in,
        price_template_id=price_template_id,
    )
    sync_category_product_count(session=session, category_id=product_in.category_id)
    return db_product
