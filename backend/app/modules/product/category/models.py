"""商品模块：商品分类数据库模型"""

import uuid
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.core.mixin.models import BaseModelMixin

if TYPE_CHECKING:
    from app.modules.product.product.models import Product


class ProductCategory(BaseModelMixin, SQLModel, table=True):
    """商品分类数据库模型"""

    __tablename__ = "product_category"

    name: str = Field(
        max_length=100,
        title="分类名称",
        description="分类名称，同一父级下应保持唯一",
    )
    parent_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="product_category.id",
        nullable=True,
        ondelete="CASCADE",
        index=True,
        title="上级分类 ID",
        description="上级分类的 UUID，为空表示顶级分类；删除父分类时级联删除子分类",
    )
    icon_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="image.id",
        nullable=True,
        ondelete="SET NULL",
        title="分类图标 ID",
        description="分类图标对应的图片资源 UUID，删除图片后置空",
    )
    product_count: int = Field(
        default=0,
        ge=0,
        title="商品数量",
        description="包含子分类的商品数量缓存，由 service 层维护",
    )
    sort: int = Field(
        default=0,
        ge=0,
        title="排序",
        description="排序权重，数值越小越靠前",
    )

    parent: ProductCategory = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "ProductCategory.id"},
    )
    children: list[ProductCategory] = Relationship(back_populates="parent")
    products: list["Product"] = Relationship(back_populates="category")  # noqa: UP037
