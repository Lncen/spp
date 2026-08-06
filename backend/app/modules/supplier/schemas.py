"""供应商模块：API 请求与响应模型"""
import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import field_validator
from sqlmodel import Field, SQLModel


class PlatformEnum(StrEnum):
    """供应商平台枚举"""
    SELF = "self" # 自营
    YLSUP = "ylsup"


class SupplierBase(SQLModel):
    """供应商基础属性——不含 balance（balance 仅通过同步接口更新）"""
    name: str = Field(max_length=255, title="供应商名称", description="供应商名称标识，全局唯一")
    platform: PlatformEnum = Field(title="平台", description="供应商平台标识")
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

    @field_validator("base_url")
    @classmethod
    def sanitize_base_url(cls, v: str) -> str:
        """自动去除 base_url 末尾的斜杠"""
        if isinstance(v, str):
            return v.rstrip("/")
        return v


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


class PlatformOption(SQLModel):
    """平台选项——供前端下拉菜单使用"""
    value: str = Field(title="平台值", description="枚举值，用于表单提交")
    label: str = Field(title="平台标签", description="展示名称，用于下拉菜单展示")


class PlatformOptionsPublic(SQLModel):
    """平台选项列表响应"""
    data: list[PlatformOption]


class BalancePublic(SQLModel):
    """供应商上游实时余额响应"""
    balance: Decimal | None = Field(title="余额", description="上游账户实时余额")


class UpstreamProductPublic(SQLModel):
    """上游商品列表项（与本地货源匹配状态）"""
    upstream_id: str = Field(title="上游商品 ID", description="上游商品 ID")
    name: str = Field(title="商品名称", description="上游商品名称")
    cost_price: Decimal | None = Field(
        default=None,
        title="成本价",
        description="上游价格；列表接口可能不返回",
    )
    synced: bool = Field(
        default=False,
        title="是否已同步",
        description="是否已存在匹配的本地商品货源",
    )
    local_product_id: uuid.UUID | None = Field(
        default=None,
        title="本地商品 ID",
        description="已同步时对应的本地商品 UUID",
    )


class UpstreamCategoryPublic(SQLModel):
    """上游商品分类选项"""

    id: str = Field(title="分类 ID", description="上游商品分类 ID")
    name: str = Field(title="分类名称", description="上游商品分类名称")
    parent_id: str | None = Field(
        default=None,
        title="父分类 ID",
        description="父分类 ID，0 或空表示顶级分类",
    )


class UpstreamCategoriesPublic(SQLModel):
    """上游商品分类列表响应"""

    data: list[UpstreamCategoryPublic]


class UpstreamProductsPublic(SQLModel):
    """上游商品列表响应"""
    data: list[UpstreamProductPublic]
    count: int


class UpstreamProductSyncRequest(SQLModel):
    """提交同步的上游商品 ID 列表"""
    product_ids: list[str] = Field(title="上游商品 ID 列表")
    category_id: uuid.UUID | None = Field(
        default=None,
        title="本地分类 ID",
        description="同步时写入商品的本地分类，不传则保持原分类",
    )


class UpstreamProductSyncPublic(SQLModel):
    """创建同步任务响应"""
    task_id: str = Field(title="Celery 任务 ID")
