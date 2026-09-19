"""授权模块：数据模型"""

from app.modules.authorization.models.role_permission import RolePermission
from app.modules.authorization.models.user_permission import UserPermission
from app.modules.authorization.models.user_role import UserRole

__all__ = ["RolePermission", "UserPermission", "UserRole"]
