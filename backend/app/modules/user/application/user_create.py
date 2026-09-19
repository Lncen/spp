"""用户模块：创建用户应用服务"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.core.security import get_password_hash
from app.init_models_data.roles import DEFAULT_USER_ROLE_CODE
from app.modules.authorization.models import UserRole
from app.modules.level.models import UserLevel
from app.modules.role.models import Role
from app.modules.user.domain.constants import default_username
from app.modules.user.infrastructure.emails import send_new_account_email
from app.modules.user.models import User
from app.modules.user.repositories.user import (
    create_user_record,
    get_user_by_email,
    get_user_by_username,
)
from app.modules.user.schemas import PrivateUserCreate, UserCreate, UserRegister


def _get_default_level_id(*, session: Session) -> uuid.UUID | None:
    """查询默认等级 ID（无默认等级时返回 None）"""
    level = session.exec(
        select(UserLevel).where(UserLevel.is_default == True)  # noqa: E712
    ).first()
    return level.id if level else None


def _assign_default_role(*, session: Session, user: User) -> None:
    """为新用户分配内置「普通用户」角色（角色未播种时跳过）"""
    role = session.exec(
        select(Role).where(col(Role.code) == DEFAULT_USER_ROLE_CODE)
    ).first()
    if role is None or user.id is None:
        return
    session.add(UserRole(user_id=user.id, role_id=role.id))


def create_user(
    *,
    session: Session,
    user_create: UserCreate,
    send_notification: bool = False,
) -> User:
    """创建新用户（超级管理员 / 种子数据共用，可选发送账号通知邮件）"""
    if get_user_by_email(session=session, email=user_create.email):
        raise HTTPException(status_code=400, detail="该邮箱已被注册")
    if user_create.username and get_user_by_username(
        session=session, username=user_create.username
    ):
        raise HTTPException(status_code=400, detail="该用户名已被使用")
    return _persist_user(
        session=session,
        user_create=user_create,
        send_notification=send_notification,
    )


def register_user(*, session: Session, user_in: UserRegister) -> User:
    """用户自助注册"""
    if get_user_by_email(session=session, email=user_in.email):
        raise HTTPException(status_code=400, detail="该邮箱已注册")
    if user_in.username and get_user_by_username(
        session=session, username=user_in.username
    ):
        raise HTTPException(status_code=400, detail="该用户名已被使用")
    user_create = UserCreate.model_validate(user_in)
    return _persist_user(session=session, user_create=user_create)


def create_user_private(*, session: Session, user_in: PrivateUserCreate) -> User:
    """内部接口：创建新用户（仅开发环境可用）"""
    user = User(
        email=user_in.email,
        username=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
    )
    user.level_id = _get_default_level_id(session=session)
    session.add(user)
    session.flush()
    _assign_default_role(session=session, user=user)
    session.commit()
    return user


def _persist_user(
    *,
    session: Session,
    user_create: UserCreate,
    send_notification: bool = False,
) -> User:
    """落库并提交，用户名缺省时默认使用邮箱，并分配默认等级"""
    username = user_create.username or default_username(user_create.email)
    user = create_user_record(
        session=session,
        user_create=user_create,
        username=username,
        hashed_password=get_password_hash(user_create.password),
    )
    user.level_id = _get_default_level_id(session=session)
    _assign_default_role(session=session, user=user)
    session.commit()
    session.refresh(user)
    if send_notification:
        send_new_account_email(email=user_create.email, password=user_create.password)
    return user
