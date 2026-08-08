"""用户模块：API 请求与响应模型"""
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr
from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    """用户基础属性"""
    username: str | None = Field(
        default=None,
        max_length=255,
        title="用户名",
        description="用户名，不填时默认使用邮箱",
    )
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    can_order: bool = True
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    """创建用户请求"""
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    """用户注册请求"""
    username: str | None = Field(
        default=None,
        max_length=255,
        title="用户名",
        description="用户名，不填时默认使用邮箱",
    )
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserUpdate(SQLModel):
    """更新用户请求（全部可选）"""
    username: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    can_order: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    """当前用户更新个人信息请求"""
    username: str | None = Field(default=None, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    """修改密码请求"""
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserPublic(UserBase):
    """用户公开响应"""
    username: str
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    """用户列表响应"""
    data: list[UserPublic]
    count: int


class PrivateUserCreate(BaseModel):
    """内部创建用户请求（仅管理员接口使用）"""
    email: str
    password: str
    full_name: str
    is_verified: bool = False
