"""用户模块：接口层"""

from app.modules.user.api.private import private_router
from app.modules.user.api.users import router

__all__ = ["private_router", "router"]
