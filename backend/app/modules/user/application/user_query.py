"""用户模块：用户查询应用服务"""

import uuid
from decimal import Decimal

from sqlmodel import Session

from app.modules.level.models import UserLevel
from app.modules.user.models import User
from app.modules.user.repositories.user import (
    count_users,
    list_wallets_by_user_ids,
)
from app.modules.user.repositories.user import (
    get_user_by_email as get_user_by_email_record,
)
from app.modules.user.repositories.user import (
    get_user_by_id as get_user_by_id_record,
)
from app.modules.user.repositories.user import (
    get_user_by_username as get_user_by_username_record,
)
from app.modules.user.repositories.user import (
    list_users as list_users_record,
)
from app.modules.user.schemas import UserDetailPublic, UserListItemPublic


def get_users_page(
    *,
    session: Session,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> tuple[int, list[UserListItemPublic]]:
    """分页查询用户列表项（含钱包余额），返回 (总数, 列表)"""
    count = count_users(session=session, search=search)
    users = list_users_record(session=session, skip=skip, limit=limit, search=search)
    wallets = list_wallets_by_user_ids(
        session=session,
        user_ids=[user.id for user in users if user.id is not None],
    )
    items = []
    for user in users:
        if user.id is None:
            continue
        wallet = wallets.get(user.id)
        items.append(
            UserListItemPublic(
                id=user.id,
                username=user.username,
                balance=wallet.balance if wallet else Decimal("0"),
                is_superuser=user.is_superuser,
                is_active=user.is_active,
            )
        )
    return count, items


def get_user_by_id(*, session: Session, user_id: uuid.UUID) -> User | None:
    """按 ID 获取用户"""
    return get_user_by_id_record(session=session, user_id=user_id)


def get_user_by_email(*, session: Session, email: str) -> User | None:
    """按邮箱获取用户"""
    return get_user_by_email_record(session=session, email=email)


def get_user_by_username(*, session: Session, username: str) -> User | None:
    """按用户名获取用户"""
    return get_user_by_username_record(session=session, username=username)


def get_user_detail(*, session: Session, user_id: uuid.UUID) -> UserDetailPublic | None:
    """获取用户详情（含等级名称），不存在返回 None"""
    user = get_user_by_id_record(session=session, user_id=user_id)
    if user is None:
        return None
    level_name = None
    if user.level_id is not None:
        level = session.get(UserLevel, user.level_id)
        level_name = level.name if level else None
    return UserDetailPublic.model_validate(user, update={"level_name": level_name})
