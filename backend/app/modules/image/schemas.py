"""图片模块：API 请求与响应模型"""
from enum import StrEnum
import uuid
from datetime import datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel


class ImageCategory(StrEnum):
    """图片分类（保留枚举用于文档参考，校验已改为 DB 驱动）"""
    AVATAR = "avatar"
    PRODUCT = "product"
    PRODUCT_DETAIL = "product_detail"


# ===================== Image (原有) =====================


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


# ===================== ImageCategory (分类管理) =====================


class ImageCategoryBase(SQLModel):
    """分类基础属性"""
    description: str | None = Field(default=None, max_length=255, title="描述")
    sort_order: int = Field(default=0, title="排序权重")
    icon: str | None = Field(default=None, max_length=64, title="图标名称")


class ImageCategoryCreate(ImageCategoryBase):
    """创建分类请求"""
    name: str = Field(
        min_length=1,
        max_length=32,
        regex=r"^[a-z][a-z0-9_]*$",
        title="分类标识",
        description="小写英文字母开头，仅允许小写字母、数字、下划线"
    )


class ImageCategoryUpdate(SQLModel):
    """更新分类请求（全部可选）"""
    description: str | None = Field(default=None, max_length=255, title="描述")
    sort_order: int | None = Field(default=None, title="排序权重")
    icon: str | None = Field(default=None, max_length=64, title="图标名称")
    is_active: bool | None = Field(default=None, title="激活状态")


class ImageCategoryPublic(ImageCategoryBase):
    """分类公开响应"""
    id: uuid.UUID
    name: str
    is_active: bool
    image_count: int
    created_at: datetime | None = None


class ImageCategoriesPublic(SQLModel):
    """分类列表响应"""
    data: list[ImageCategoryPublic]
    count: int
