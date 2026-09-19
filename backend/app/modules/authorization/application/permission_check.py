"""授权模块：权限检查应用服务

读取链路：缓存 → 数据库（角色授予 ∪ 用户直授） → 授权规则判定。
"""

import uuid
from collections.abc import Iterable

from sqlmodel import Session

from app.modules.authorization.domain.authorization import is_permission_granted
from app.modules.authorization.infrastructure import cache
from app.modules.authorization.repositories.grant import (
    list_active_user_ids_by_permission_code,
    list_user_effective_permission_codes,
)
from app.modules.permission.application.permission_query import (
    get_active_permission_codes,
)
from app.modules.user.models import User


def get_user_permission_codes(*, session: Session, user: User) -> set[str]:
    """用户有效权限码：超管返回全部有效权限码，其余用户缓存优先"""
    if user.is_superuser:
        return get_active_permission_codes(session=session)
    cached = cache.get_user_permission_codes(user_id=user.id)
    if cached is not None:
        return cached
    codes = list_user_effective_permission_codes(session=session, user_id=user.id)
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


def has_any_permission(
    *, session: Session, user: User, codes: Iterable[str]
) -> bool:
    """判断用户是否持有任意一个权限码

    有效权限码只取一次（命中缓存），避免逐码查询；停用账号与超管的判定仍走领域规则。
    """
    permission_codes: set[str] = set()
    if user.is_active and not user.is_superuser:
        permission_codes = get_user_permission_codes(session=session, user=user)
    return any(
        is_permission_granted(
            code=code,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            permission_codes=permission_codes,
        )
        for code in codes
    )


def list_active_user_ids_with_permission(
    *, session: Session, code: str
) -> list[uuid.UUID]:
    """持有指定权限码的启用用户 ID，供按权限圈定某类操作人的业务使用"""
    return list_active_user_ids_by_permission_code(session=session, code=code)
