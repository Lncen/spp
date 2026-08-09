from fastapi import APIRouter

from app.common.router import router as utils_router
from app.core.config import settings
from app.modules.auth.router import login_router, password_router, token_router
from app.modules.image.models import Image, ImageCategory  # noqa: F401
from app.modules.image.router import (
    category_router as image_category_router,
)
from app.modules.image.router import (
    router as image_router,
)
from app.modules.item.models import Item  # noqa: F401
from app.modules.item.router import router as item_router
from app.modules.level.models import UserLevel  # noqa: F401
from app.modules.level.router import router as level_router
from app.modules.order.models import Order  # noqa: F401
from app.modules.order.router import router as order_router
from app.modules.price_template.models import (  # noqa: F401
    PriceTemplate,
    PriceTemplateRule,
)
from app.modules.price_template.router import router as price_template_router
from app.modules.product.category.models import ProductCategory  # noqa: F401
from app.modules.product.category.router import (
    category_router as product_category_router,
)
from app.modules.product.product.models import (  # noqa: F401
    Product,
    ProductBuyParam,
    ProductFulfillment,
    ProductInventory,
    ProductPricing,
    ProductSupplier,
)
from app.modules.product.product.router import product_router
from app.modules.schedule.router import router as schedule_router
from app.modules.schedule.runs import router as schedule_runs_router
from app.modules.schedule.tasks import router as schedule_tasks_router
from app.modules.setting.router import router as setting_router
from app.modules.supplier.models import Supplier  # noqa: F401
from app.modules.supplier.router import router as supplier_router
from app.modules.user.models import User  # noqa: F401
from app.modules.user.router import private_router
from app.modules.user.router import router as user_router
from app.modules.wallet.models import Wallet, WalletTransaction  # noqa: F401
from app.modules.wallet.router import router as wallet_router

api_router = APIRouter()
api_router.include_router(login_router)
api_router.include_router(password_router)
api_router.include_router(token_router)
api_router.include_router(user_router)
api_router.include_router(wallet_router)
api_router.include_router(utils_router)
api_router.include_router(level_router)
api_router.include_router(item_router)
api_router.include_router(order_router)
api_router.include_router(image_router)
api_router.include_router(image_category_router)
api_router.include_router(price_template_router)
api_router.include_router(schedule_router)
api_router.include_router(schedule_runs_router)
api_router.include_router(schedule_tasks_router)
api_router.include_router(setting_router)
api_router.include_router(supplier_router)
api_router.include_router(product_router)
api_router.include_router(product_category_router)

if settings.ENVIRONMENT == "local":
    api_router.include_router(private_router)
