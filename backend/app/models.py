"""数据库模型聚合文件——兼容 Alembic 自动迁移

此文件仅导入并注册所有 SQLModel 表模型，
让 Alembic 的 env.py 能够通过 `from app.models import SQLModel`
获取完整的 metadata。
"""

from sqlmodel import SQLModel

from app.modules.image.models import Image, ImageCategory
from app.modules.item.models import Item
from app.modules.level.models import UserLevel
from app.modules.order.models import Order, OrderItem
from app.modules.price_template.models import PriceTemplate, PriceTemplateRule
from app.modules.product.category.models import ProductCategory
from app.modules.product.product.models import (
    Product,
    ProductBuyParam,
    ProductFulfillment,
    ProductInventory,
    ProductPricing,
    ProductSupplier,
)
from app.modules.supplier.models import Supplier
from app.modules.user.models import User
from app.modules.wallet.models import Wallet, WalletTransaction

__all__ = [
    "SQLModel",
    "UserLevel",
    "Item",
    "User",
    "Image",
    "ImageCategory",
    "Supplier",
    "Order",
    "OrderItem",
    "PriceTemplate",
    "PriceTemplateRule",
    "ProductCategory",
    "Product",
    "ProductSupplier",
    "ProductPricing",
    "ProductInventory",
    "ProductFulfillment",
    "ProductBuyParam",
    "Wallet",
    "WalletTransaction",
]
