"""图片模块：API 请求与响应模型"""
import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class ImageBase(SQLModel):
    """图片基础属性"""
    filename: str = Field(max_length=255)
    file_size: int
    width: int
    height: int


class ImagePublic(ImageBase):
    """图片公开响应"""
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None
    url: str


class ImagesPublic(SQLModel):
    """图片列表响应"""
    data: list[ImagePublic]
    count: int
