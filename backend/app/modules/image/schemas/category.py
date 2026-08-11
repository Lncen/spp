"""图片模块：分类请求与响应模型"""
import re
import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import field_validator
from sqlmodel import Field, SQLModel


_CATEGORY_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class ImageCategory(StrEnum):
    """图片分类（保留枚举用于文档参考，校验已改为 DB 驱动）"""
    AVATAR = "avatar"
    PRODUCT = "product"
    PRODUCT_DETAIL = "product_detail"


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
        title="分类标识",
        description="小写英文字母开头，仅允许小写字母、数字、下划线"
    )

    @field_validator("name")
    @classmethod
    def _validate_name_pattern(cls, value: str) -> str:
        if not _CATEGORY_NAME_PATTERN.match(value):
            raise ValueError("分类标识需以小写字母开头，仅允许小写字母、数字、下划线")
        return value


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
