from sqlmodel import Field

from app.core.mixin.models import BaseModelMixin
from app.modules.level.schemas import LevelBase


class UserLevel(BaseModelMixin, LevelBase, table=True):
    """用户等级数据库模型"""

    __tablename__ = "user_level"

    level: int = Field(
        unique=True,
        ge=1,
        le=10,
        title="等级编号",
        description="等级编号 1～10，固定不可增减"
    )
    name: str = Field(
        max_length=255,
        title="等级名称",
        description="等级名称，如「练气期」「筑基期」"
    )
    description: str | None = Field(
        default=None,
        max_length=255,
        title="等级描述",
        description="对当前等级的详细说明"
    )
    is_default: bool = Field(
        default=False,
        title="是否默认",
        description="新用户注册时默认分配的等级（仅允许一个等级为 True）"
    )

    # 等级 ID 作为 User 模型的外键引用，此处不需要反向关系
