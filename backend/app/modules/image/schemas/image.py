"""图片模块：图片请求与响应模型"""
import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class ImageBase(SQLModel):
    """图片基础属性"""
    filename: str = Field(max_length=255)
    file_size: int
    width: int
    height: int
    category: str | None = Field(default=None, max_length=32, title="分类")


class ImageUpdate(SQLModel):
    """更新图片请求"""
    category: str | None = Field(default=None, max_length=32, title="分类")


class ImagePublic(SQLModel):
    """图片公开响应"""
    id: uuid.UUID
    url: str
    filename: str
    file_size: int
    width: int
    height: int
    category: str | None = Field(default=None, max_length=32, title="分类")
    created_at: datetime | None = None


class ImagesPublic(SQLModel):
    """图片列表响应"""
    data: list[ImagePublic]
    count: int
