"""物品模块：数据库模型"""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship

if TYPE_CHECKING:
    from app.modules.user.models import User

from app.core.mixin.models import BaseModelMixin
from app.modules.item.schemas import ItemBase


class Item(BaseModelMixin, ItemBase, table=True):
    """物品数据库模型"""

    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
        title="所有者 ID",
        description="物品所属用户的 UUID。当该用户被删除时，其名下物品将被级联删除"
    )

    # 关系字段不需要也不支持 Field 参数，保持原样即可
    owner: Optional["User"] = Relationship(back_populates="items")
    image_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="image.id",
        nullable=True,
        ondelete="SET NULL",
        title="配图图片 ID",
        description="物品关联的图片资源 UUID。删除该图片后此字段置空"
    )
