"""用户模块：业务逻辑层"""
from typing import Any

from sqlmodel import Session, select

from app.core.security import get_password_hash
from app.modules.user.models import User
from app.modules.user.schemas import UserCreate, UserUpdate


def create_user(*, session: Session, user_create: UserCreate) -> User:
    """创建新用户"""
    username = getattr(user_create, "username", None) or user_create.email
    db_obj = User.model_validate(
        user_create,
        update={
            "hashed_password": get_password_hash(user_create.password),
            "username": username,
        },
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    """更新用户信息"""
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    """根据邮箱获取用户"""
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()
