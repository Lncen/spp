"""图片模块：接口层"""

from app.modules.image.api.categories import category_router
from app.modules.image.api.images import router

__all__ = ["category_router", "router"]
