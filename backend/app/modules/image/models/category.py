"""图片模块：分类数据库模型"""
from sqlmodel import Field

from app.core.mixin.models import BaseModelMixin
from app.modules.image.schemas import ImageCategoryBase


class ImageCategory(BaseModelMixin, ImageCategoryBase, table=True):
    """图片分类数据库模型"""
    name: str = Field(
        unique=True,
        max_length=32,
        index=True,
        title="分类标识",
        description="分类的唯一标识键，与 Image.category 字段的值对应"
    )
    image_count: int = Field(
        default=0,
        title="图片数量",
        description="该分类下的图片数量（缓存计数，由应用层更新）"
    )
