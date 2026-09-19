"""授权模块：接口层"""

from app.modules.authorization.api.role_permissions import role_permission_router
from app.modules.authorization.api.user_grants import user_grant_router

__all__ = ["role_permission_router", "user_grant_router"]
