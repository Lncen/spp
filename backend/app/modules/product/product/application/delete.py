"""商品模块：删除商品应用服务"""

import uuid

from sqlmodel import Session

from app.modules.product.category.service import sync_category_product_count
from app.modules.product.product.repositories.product import (
    delete_product_configs,
    get_product_or_404,
)


def delete_product(*, session: Session, product_id: uuid.UUID) -> None:
    """删除商品及其关联配置"""
    db_product = get_product_or_404(session=session, product_id=product_id)
    category_id = db_product.category_id
    delete_product_configs(session=session, product_id=product_id)
    session.delete(db_product)
    session.commit()
    sync_category_product_count(session=session, category_id=category_id)
