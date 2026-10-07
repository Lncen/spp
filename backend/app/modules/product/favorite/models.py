"""商品模块：商品收藏数据库模型"""

import uuid

from sqlmodel import Field, SQLModel, UniqueConstraint

from app.core.mixin.models import BaseModelMixin


class ProductFavorite(BaseModelMixin, SQLModel, table=True):
    """用户商品收藏数据库模型，同一用户对同一商品至多一条记录"""

    __tablename__ = "product_favorite"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "product_id",
            name="uq_product_favorite_user_product",
        ),
    )

    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
        index=True,
        title="用户 ID",
        description="收藏人的 UUID，删除用户时级联删除收藏",
    )
    product_id: uuid.UUID = Field(
        foreign_key="product.id",
        nullable=False,
        ondelete="CASCADE",
        index=True,
        title="商品 ID",
        description="被收藏商品的 UUID，删除商品时级联删除收藏",
    )
