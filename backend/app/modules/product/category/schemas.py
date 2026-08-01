"""商品模块：商品分类 API 请求与响应模型"""

import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class ProductCategoryCreate(SQLModel):
    """创建商品分类请求"""

    name: str = Field(
        min_length=1,
        max_length=100,
        title="分类名称",
        description="分类名称，同一父级下应保持唯一",
    )
    parent_id: uuid.UUID | None = Field(
        default=None,
        title="上级分类 ID",
        description="为空表示顶级分类",
    )
    icon_id: uuid.UUID | None = Field(
        default=None,
        title="分类图标 ID",
        description="分类图标对应的图片资源 UUID",
    )
    sort: int = Field(default=0, ge=0, title="排序", description="数值越小越靠前")
    is_active: bool = Field(default=True, title="是否启用")


class ProductCategoryUpdate(SQLModel):
    """更新商品分类请求（全部可选）"""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        title="分类名称",
    )
    parent_id: uuid.UUID | None = Field(default=None, title="上级分类 ID")
    icon_id: uuid.UUID | None = Field(default=None, title="分类图标 ID")
    sort: int | None = Field(default=None, ge=0, title="排序")
    is_active: bool | None = Field(default=None, title="是否启用")


class ProductCategoryPublic(SQLModel):
    """商品分类公开响应"""

    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    icon_id: uuid.UUID | None
    icon_url: str | None = None
    product_count: int
    sort: int
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductCategoryTreePublic(ProductCategoryPublic):
    """商品分类树节点响应"""

    children: list[ProductCategoryTreePublic] = Field(
        default_factory=list,
        title="子分类",
        description="按 sort 排序的子分类树节点",
    )


class ProductCategoriesPublic(SQLModel):
    """商品分类列表响应"""

    data: list[ProductCategoryTreePublic]
    count: int
