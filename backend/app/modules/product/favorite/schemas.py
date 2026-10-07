"""商品模块：商品收藏 API 请求与响应模型"""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel

from app.modules.product.constants import ProductStatus


class ProductFavoriteCreate(SQLModel):
    """收藏商品请求"""

    product_id: uuid.UUID = Field(
        title="商品 ID",
        description="要收藏的商品 UUID",
    )


class ProductFavoritePublic(SQLModel):
    """收藏记录响应，仅暴露用户可见的商品展示字段"""

    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    image_url: str | None = None
    category_id: uuid.UUID | None = None
    status: ProductStatus
    is_closed: bool
    created_at: datetime | None = None


class ProductFavoritesPublic(SQLModel):
    """收藏列表响应"""

    data: list[ProductFavoritePublic]
    count: int


class ProductFavoriteStatusPublic(SQLModel):
    """收藏状态响应"""

    product_id: uuid.UUID
    favorited: bool
