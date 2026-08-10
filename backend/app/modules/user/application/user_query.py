"""用户模块：用户查询应用服务"""

import uuid

from sqlmodel import Session

from app.modules.user.models import User
from app.modules.user.repositories.user import (
    count_users,
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


def get_users_page(
    *, session: Session, skip: int = 0, limit: int = 100
) -> tuple[int, list[User]]:
    """分页查询用户，返回 (总数, 用户列表)"""
    count = count_users(session=session)
    users = list_users_record(session=session, skip=skip, limit=limit)
    return count, users


def get_user_by_id(*, session: Session, user_id: uuid.UUID) -> User | None:
    """按 ID 获取用户"""
    return get_user_by_id_record(session=session, user_id=user_id)


def get_user_by_email(*, session: Session, email: str) -> User | None:
    """按邮箱获取用户"""
    return get_user_by_email_record(session=session, email=email)


def get_user_by_username(*, session: Session, username: str) -> User | None:
    """按用户名获取用户"""
    return get_user_by_username_record(session=session, username=username)
