"""物品模块：API 请求与响应模型"""
import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class ItemBase(SQLModel):
    """物品基础属性"""
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)



class ItemCreate(ItemBase):
    """创建物品请求"""
    pass


class ItemUpdate(SQLModel):
    """更新物品请求（全部可选）"""
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    image_id: uuid.UUID | None = Field(default=None, title="配图图片 ID")


class ItemPublic(ItemBase):
    """物品公开响应"""
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None
    image_id: uuid.UUID | None = None
    image_url: str | None = None


class ItemsPublic(SQLModel):
    """物品列表响应"""
    data: list[ItemPublic]
    count: int
