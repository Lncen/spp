"""商品模块：面向用户的商品展示信息拼装

收藏与组合都以「商品 ID + 用户可见展示字段」的形式回给用户，这里统一批量拼装，
避免各子模块各写一份；同时确保不下发成本价、供应商 SKU 等内部字段。
"""

import uuid
from dataclasses import dataclass

from sqlmodel import Session, select

from app.core.config import settings
from app.modules.image.models import Image
from app.modules.product.product.models import Product
from app.modules.product.product.repositories.product import get_images_map


@dataclass(frozen=True)
class ProductDisplay:
    """商品对用户可见的展示信息"""

    product: Product
    image_url: str | None


def build_image_url(image: Image) -> str:
    """构建图片访问 URL"""
    if settings.STATIC_URL_BASE:
        base = settings.STATIC_URL_BASE.rstrip("/")
        return f"{base}/uploads/{image.file_path}"
    return f"/uploads/{image.file_path}"


def load_product_displays(
    *, session: Session, product_ids: set[uuid.UUID]
) -> dict[uuid.UUID, ProductDisplay]:
    """按商品 ID 批量加载商品与主图 URL，避免 N+1"""
    if not product_ids:
        return {}
    products = session.exec(select(Product).where(Product.id.in_(product_ids))).all()
    image_ids = {product.image_id for product in products if product.image_id}
    images = get_images_map(session=session, image_ids=image_ids)
    return {
        product.id: ProductDisplay(
            product=product,
            image_url=(
                build_image_url(images[product.image_id])
                if product.image_id in images
                else None
            ),
        )
        for product in products
    }
