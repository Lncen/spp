"""用户模块：数据访问层"""

import uuid
from typing import Any

from sqlmodel import Session, col, delete, func, select

from app.modules.item.models import Item
from app.modules.user.models import User
from app.modules.user.schemas import UserCreate


def count_users(*, session: Session) -> int:
    """统计用户总数"""
    return session.exec(select(func.count()).select_from(User)).one()


def list_users(*, session: Session, skip: int = 0, limit: int = 100) -> list[User]:
    """按创建时间倒序分页查询用户"""
    statement = (
        select(User).order_by(col(User.created_at).desc()).offset(skip).limit(limit)
    )
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


def delete_user_record(*, session: Session, user: User, user_id: uuid.UUID) -> None:
    """删除用户及其关联 items（不提交，由应用层控制事务）"""
    statement = delete(Item).where(col(Item.owner_id) == user_id)
    session.exec(statement)
    session.delete(user)
    session.flush()


def delete_user_account(*, session: Session, user: User) -> None:
    """仅删除用户记录（不提交，由应用层控制事务）"""
    session.delete(user)
    session.flush()
