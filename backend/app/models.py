"""数据库模型聚合文件——兼容 Alembic 自动迁移

此文件仅导入并注册所有 SQLModel 表模型，
让 Alembic 的 env.py 能够通过 `from app.models import SQLModel`
获取完整的 metadata。
"""

from sqlmodel import SQLModel

from app.modules.auth.models import RefreshToken
from app.modules.automation.models import (
    AutomationEvent,
    AutomationRule,
    AutomationTask,
    AutomationTaskArchive,
)
from app.modules.customer_service.models import (
    Conversation,
    ConversationMessage,
)
from app.modules.image.models import Image, ImageCategory
from app.modules.level.models import UserLevel
from app.modules.notification.models import (
    Notification,
    NotificationDelivery,
)
from app.modules.order.models import Order, OrderParam
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
from app.modules.setting.models import AppSetting
from app.modules.supplier.models import Supplier
from app.modules.user.models import User
from app.modules.wallet.models import Wallet, WalletTransaction

__all__ = [
    "SQLModel",
    "RefreshToken",
    "AutomationTask",
    "AutomationTaskArchive",
    "AutomationEvent",
    "AutomationRule",
    "Conversation",
    "ConversationMessage",
    "UserLevel",
    "Notification",
    "NotificationDelivery",
    "User",
    "Image",
    "ImageCategory",
    "Supplier",
    "AppSetting",
    "Order",
    "OrderParam",
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
