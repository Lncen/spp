
from fastapi import APIRouter

from app.common.router import router as utils_router
from app.core.config import settings
from app.modules.auth.router import router as login_router
from app.modules.image.models import Image, ImageCategory  # noqa: F401
from app.modules.image.router import (
    router as image_router,
    category_router as image_category_router,
)
from app.modules.level.models import UserLevel  # noqa: F401
from app.modules.level.router import router as level_router
from app.modules.item.models import Item  # noqa: F401
from app.modules.item.router import router as item_router
from app.modules.supplier.models import Supplier  # noqa: F401
from app.modules.supplier.router import router as supplier_router
from app.modules.user.models import User  # noqa: F401
from app.modules.user.router import private_router
from app.modules.user.router import router as user_router

api_router = APIRouter()
api_router.include_router(login_router)
api_router.include_router(user_router)
api_router.include_router(utils_router)
api_router.include_router(level_router)
api_router.include_router(item_router)
api_router.include_router(image_router)
api_router.include_router(image_category_router)
api_router.include_router(supplier_router)

if settings.ENVIRONMENT == "local":
    api_router.include_router(private_router)
