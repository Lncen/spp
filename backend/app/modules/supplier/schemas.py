"""供应商模块：API 请求与响应模型"""
import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlmodel import Field, SQLModel


class PlatformEnum(StrEnum):
    """供应商平台枚举"""
    YLSUP = "ylsup"


class SupplierBase(SQLModel):
    """供应商基础属性——不含 balance（balance 仅通过同步接口更新）"""
    platform: PlatformEnum = Field(title="平台", description="供应商平台标识")
    name: str = Field(max_length=255, title="供应商名称", description="供应商名称标识")
    base_url: str = Field(max_length=512, title="API 基础地址", description="API 请求的基础 URL")
    app_key: str = Field(max_length=512, title="应用密钥 Key", description="API 认证密钥 Key")
    app_secret: str = Field(max_length=512, title="应用密钥 Secret", description="API 认证密钥 Secret，响应中脱敏")
    status: str = Field(default="active", max_length=32, title="状态", description="active=启用中, inactive=已停用, suspended=异常冻结")
    connection_status: str = Field(default="unknown", max_length=32, title="连接状态", description="online=可达, offline=不可达, unknown=未知")
    timeout_seconds: int = Field(default=30, ge=1, le=300, title="超时秒数", description="API 请求超时时间")
    retry_times: int = Field(default=3, ge=0, le=10, title="重试次数", description="请求失败时的重试次数")
    description: str | None = Field(default=None, max_length=1024, title="描述", description="备注说明")


class SupplierCreate(SupplierBase):
    """创建供应商请求"""
    pass


class SupplierUpdate(SQLModel):
    """更新供应商请求（全部可选，不含 balance）"""
    platform: PlatformEnum | None = Field(default=None)
    name: str | None = Field(default=None, max_length=255)
    base_url: str | None = Field(default=None, max_length=512)
    app_key: str | None = Field(default=None, max_length=512)
    app_secret: str | None = Field(default=None, max_length=512)
    status: str | None = Field(default=None, max_length=32)
    connection_status: str | None = Field(default=None, max_length=32)
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)
    retry_times: int | None = Field(default=None, ge=0, le=10)
    description: str | None = Field(default=None, max_length=1024)


class SupplierPublic(SupplierBase):
    """供应商公开响应"""
    id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_active: bool = True
    balance: Decimal | None = None


class SuppliersPublic(SQLModel):
    """供应商列表响应"""
    data: list[SupplierPublic]
    count: int


class SupplierBalancePublic(SQLModel):
    """余额同步响应"""
    id: uuid.UUID
    name: str
    balance: Decimal | None = None
    message: str = "余额已同步"


class PlatformOption(SQLModel):
    """平台选项——供前端下拉菜单使用"""
    value: str = Field(title="平台值", description="枚举值，用于表单提交")
    label: str = Field(title="平台标签", description="展示名称，用于下拉菜单展示")


class PlatformOptionsPublic(SQLModel):
    """平台选项列表响应"""
    data: list[PlatformOption]
