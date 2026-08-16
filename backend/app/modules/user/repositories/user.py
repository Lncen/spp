"""用户模块：数据访问层"""

import uuid
from typing import Any

from sqlmodel import Session, col, func, or_, select

from app.modules.user.models import User
from app.modules.user.schemas import UserCreate
from app.modules.wallet.models import Wallet


def _search_filter(search: str | None):
    """构造用户名/邮箱/昵称模糊匹配条件，无搜索词时返回 None"""
    if not search:
        return None
    pattern = f"%{search.strip()}%"
    return or_(
        User.username.ilike(pattern),
        User.email.ilike(pattern),
        User.full_name.ilike(pattern),
    )


def count_users(*, session: Session, search: str | None = None) -> int:
    """统计用户总数"""
    statement = select(func.count()).select_from(User)
    search_filter = _search_filter(search)
    if search_filter is not None:
        statement = statement.where(search_filter)
    return session.exec(statement).one()


def list_users(
    *,
    session: Session,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> list[User]:
    """按创建时间倒序分页查询用户"""
    statement = select(User).order_by(col(User.created_at).desc())
    search_filter = _search_filter(search)
    if search_filter is not None:
        statement = statement.where(search_filter)
    statement = statement.offset(skip).limit(limit)
    return list(session.exec(statement).all())


def get_user_by_id(*, session: Session, user_id: uuid.UUID) -> User | None:
    """按 ID 获取用户"""
    return session.get(User, user_id)


def get_user_by_email(*, session: Session, email: str) -> User | None:
    """按邮箱获取用户"""
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()


def get_user_by_username(*, session: Session, username: str) -> User | None:
    """按用户名获取用户"""
    statement = select(User).where(User.username == username)
    return session.exec(statement).first()


def list_wallets_by_user_ids(
    *, session: Session, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Wallet]:
    """按用户 ID 批量查询钱包，返回 {user_id: wallet}"""
    if not user_ids:
        return {}
    statement = select(Wallet).where(col(Wallet.user_id).in_(user_ids))
    return {wallet.user_id: wallet for wallet in session.exec(statement).all()}


def create_user_record(
    *,
    session: Session,
    user_create: UserCreate,
    username: str,
    hashed_password: str,
) -> User:
    """新增用户（不提交，由应用层控制事务）"""
    db_obj = User.model_validate(
        user_create,
        update={
            "hashed_password": hashed_password,
            "username": username,
        },
    )
    session.add(db_obj)
    session.flush()
    return db_obj


def update_user_record(
    *,
    session: Session,
    db_user: User,
    user_data: dict[str, Any],
    extra_data: dict[str, Any] | None = None,
) -> User:
    """更新用户字段（不提交，由应用层控制事务）"""
    db_user.sqlmodel_update(user_data, update=extra_data or {})
    session.add(db_user)
    session.flush()
    return db_user


def delete_user_record(*, session: Session, user: User) -> None:
    """删除用户记录（不提交，由应用层控制事务）"""
    session.delete(user)
    session.flush()


def delete_user_account(*, session: Session, user: User) -> None:
    """仅删除用户记录（不提交，由应用层控制事务）"""
    session.delete(user)
    session.flush()
