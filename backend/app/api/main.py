"""API 路由注册入口"""
from fastapi import APIRouter

from app.common.router import router as utils_router
from app.core.config import settings
from app.modules.auth.router import router as login_router
from app.modules.image.models import Image  # noqa: F401
from app.modules.image.router import router as image_router

# 确保所有数据库模型在路由加载前完成注册，避免 SQLAlchemy 双向关系解析失败
from app.modules.item.models import Item  # noqa: F401
from app.modules.item.router import router as item_router
from app.modules.user.models import User  # noqa: F401
from app.modules.user.router import private_router
from app.modules.user.router import router as user_router

api_router = APIRouter()
api_router.include_router(login_router)
api_router.include_router(user_router)
api_router.include_router(utils_router)
api_router.include_router(item_router)
api_router.include_router(image_router)

if settings.ENVIRONMENT == "local":
    api_router.include_router(private_router)
