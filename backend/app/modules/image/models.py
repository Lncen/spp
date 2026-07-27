"""图片模块：数据库模型"""
import uuid
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship

if TYPE_CHECKING:
    from app.modules.user.models import User

from app.core.mixin.models import BaseModelMixin
from app.modules.image.schemas import ImageBase, ImageCategoryBase


class Image(BaseModelMixin, ImageBase, table=True):
    """图片数据库模型"""

    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
        title="所有者 ID",
        description="图片所属用户的 UUID。当该用户被删除时，其名下图片将被级联删除"
    )
    file_hash: str = Field(
        max_length=64,
        unique=True,
        index=True,
        title="文件哈希",
        description="SHA256 文件内容哈希，用于图片去重"
    )
    file_path: str = Field(
        max_length=512,
        title="存储路径",
        description="图片在磁盘上的相对存储路径"
    )
    category: str | None = Field(
        default=None,
        max_length=32,
        index=True,
        title="分类",
        description="图片分类：avatar-头像, product-商品, product_detail-商品详情"
    )

    owner: Optional["User"] = Relationship(back_populates="images")
    # NOTE: 如果将来需要 Image → ImageCategory 的 FK 关系，请在此处添加 category_rel 字段


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
        description="该分类下的图片数量（缓存计数，由 service 层更新）"
    )
