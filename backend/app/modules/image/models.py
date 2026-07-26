"""图片模块：数据库模型"""
import uuid
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship

if TYPE_CHECKING:
    from app.modules.user.models import User

from app.core.mixin.models import BaseModelMixin
from app.modules.image.schemas import ImageBase


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

    owner: Optional["User"] = Relationship(back_populates="images")
