from fastapi import APIRouter

import app.modules.automation.infrastructure.event_listeners  # noqa: F401  注册事件监听器
import app.modules.customer_service.infrastructure.room_guard  # noqa: F401  注册实时会话守卫
import app.modules.notification.infrastructure.event_listeners  # noqa: F401  注册通知事件监听器
import app.modules.system_log.infrastructure.event_listeners  # noqa: F401  注册系统日志监听器
from app.common.router import router as utils_router
from app.core.config import settings
from app.modules.auth.api import login_router, password_router, token_router
from app.modules.automation.api import (
    automation_events_router,
    automation_router,
    automation_rules_router,
    schedule_router,
    schedule_tasks_router,
)
from app.modules.backup.api import router as backup_router
from app.modules.customer_service.api import router as customer_service_router
from app.modules.image.api import (
    category_router as image_category_router,
)
from app.modules.image.api import (
    router as image_router,
)
from app.modules.image.models import Image, ImageCategory  # noqa: F401
from app.modules.level.api import router as level_router
from app.modules.level.models import UserLevel  # noqa: F401
from app.modules.notification.api import router as notification_router
from app.modules.notification.models import (  # noqa: F401
    Notification,
    NotificationDelivery,
)
from app.modules.order.api import router as order_router
from app.modules.order.models import Order  # noqa: F401
from app.modules.price_template.api import router as price_template_router
from app.modules.price_template.models import (  # noqa: F401
    PriceTemplate,
    PriceTemplateRule,
)
from app.modules.product.category.api import (
    category_router as product_category_router,
)
from app.modules.product.category.models import ProductCategory  # noqa: F401
from app.modules.product.product.api import product_router
from app.modules.product.product.models import (  # noqa: F401
    Product,
    ProductBuyParam,
    ProductFulfillment,
    ProductInventory,
    ProductPricing,
    ProductSupplier,
)
from app.modules.setting.api import router as setting_router
from app.modules.supplier.api import router as supplier_router
from app.modules.supplier.models import Supplier  # noqa: F401
from app.modules.system_log.api import router as system_log_router
from app.modules.system_log.models import (  # noqa: F401
    AuditLog,
    SystemLog,
)
from app.modules.user.api import private_router
from app.modules.user.api import router as user_router
from app.modules.user.models import User  # noqa: F401
from app.modules.wallet.api import router as wallet_router
from app.modules.wallet.models import Wallet, WalletTransaction  # noqa: F401

api_router = APIRouter()
api_router.include_router(backup_router)
api_router.include_router(login_router)
api_router.include_router(password_router)
api_router.include_router(token_router)
api_router.include_router(user_router)
api_router.include_router(wallet_router)
api_router.include_router(utils_router)
api_router.include_router(level_router)
api_router.include_router(notification_router)
api_router.include_router(customer_service_router)
api_router.include_router(order_router)
api_router.include_router(image_router)
api_router.include_router(image_category_router)
api_router.include_router(price_template_router)
api_router.include_router(schedule_router)
api_router.include_router(schedule_tasks_router)
api_router.include_router(automation_router)
api_router.include_router(automation_events_router)
api_router.include_router(automation_rules_router)
api_router.include_router(setting_router)
api_router.include_router(supplier_router)
api_router.include_router(system_log_router)
api_router.include_router(product_router)
api_router.include_router(product_category_router)

if settings.ENVIRONMENT == "local":
    api_router.include_router(private_router)
