"""供应商模块：数据库模型"""

from decimal import Decimal

from sqlmodel import Field

from app.core.mixin.models import BaseModelMixin
from app.modules.supplier.schemas import SupplierBase


class Supplier(BaseModelMixin, SupplierBase, table=True):
    """供应商数据库模型"""

    __tablename__ = "supplier"

    name: str = Field(
        unique=True,
        max_length=255,
        title="供应商名称",
        description="供应商名称标识，全局唯一",
    )
    balance: Decimal | None = Field(
        default=None,
        max_digits=12,
        decimal_places=7,
        title="余额",
        description="供应商账户余额，通过 API 同步更新，不可手动修改",
    )
