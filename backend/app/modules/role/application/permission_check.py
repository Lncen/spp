"""角色模块：权限检查应用服务

读取链路：缓存 → 数据库 → 授权规则判定。
"""

from sqlmodel import Session

from app.modules.permission.application.permission_query import (
    get_active_permission_codes,
)
from app.modules.role.domain.authorization import is_permission_granted
from app.modules.role.infrastructure import cache
from app.modules.role.repositories.role import (
    get_user_permission_codes as get_user_permission_codes_from_db,
)
from app.modules.user.models import User


def get_user_permission_codes(*, session: Session, user: User) -> set[str]:
    """用户有效权限码：超管返回全部有效权限码，其余用户缓存优先"""
    if user.is_superuser:
        return get_active_permission_codes(session=session)
    cached = cache.get_user_permission_codes(user_id=user.id)
    if cached is not None:
        return cached
    codes = get_user_permission_codes_from_db(session=session, user_id=user.id)
    cache.set_user_permission_codes(user_id=user.id, codes=codes)
    return codes


def has_permission(*, session: Session, user: User, code: str) -> bool:
    """判断用户是否持有指定权限码"""
    permission_codes: set[str] = set()
    if user.is_active and not user.is_superuser:
        permission_codes = get_user_permission_codes(session=session, user=user)
    return is_permission_granted(
        code=code,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        permission_codes=permission_codes,
    )
