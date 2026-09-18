"""角色模块：接口层"""

from app.modules.role.api.roles import role_router, user_role_router

__all__ = ["role_router", "user_role_router"]
