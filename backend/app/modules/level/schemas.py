"""用户等级模块：API 请求与响应模型"""

from sqlmodel import Field, SQLModel


class LevelBase(SQLModel):
    """等级基础属性"""
    level: int = Field(ge=1, le=10, title="等级编号", description="等级编号，范围 1～10，固定不可修改")
    name: str = Field(max_length=255, title="等级名称", description="等级名称，如「练气期」")
    description: str | None = Field(default=None, max_length=255, title="等级描述")
    is_default: bool = Field(default=False, title="是否默认", description="是否为新用户的默认等级")


class LevelUpdate(SQLModel):
    """更新等级请求（全部可选）"""
    name: str | None = Field(default=None, max_length=255, title="等级名称")
    description: str | None = Field(default=None, max_length=255, title="等级描述")
    is_default: bool | None = Field(default=None, title="是否默认")


class LevelPublic(LevelBase):
    """等级公开响应"""
    id: str  # UUID 字符串形式


class LevelsPublic(SQLModel):
    """等级列表响应"""
    data: list[LevelPublic]
    count: int
