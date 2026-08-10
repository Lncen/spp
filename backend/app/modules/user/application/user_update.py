"""用户模块：更新用户应用服务"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session

from app.core.security import get_password_hash, verify_password
from app.modules.image.models import Image
from app.modules.level.models import UserLevel
from app.modules.user.models import User
from app.modules.user.repositories.user import (
    get_user_by_email,
    get_user_by_username,
    update_user_record,
)
from app.modules.user.schemas import UpdatePassword, UserUpdate, UserUpdateMe


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> User:
    """更新用户信息（超级管理员接口与密码重置共用）"""
    _check_email_username_unique(
        session=session,
        user_id=db_user.id,
        email=user_in.email,
        username=user_in.username,
    )
    _check_level(session=session, level_id=user_in.level_id)
    _check_avatar(session=session, avatar_id=user_in.avatar_id)
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        extra_data["hashed_password"] = get_password_hash(user_data["password"])
    user = update_user_record(
        session=session,
        db_user=db_user,
        user_data=user_data,
        extra_data=extra_data,
    )
    session.commit()
    session.refresh(user)
    return user


def update_user_me(
    *, session: Session, current_user: User, user_in: UserUpdateMe
) -> User:
    """更新当前用户个人信息"""
    _check_email_username_unique(
        session=session,
        user_id=current_user.id,
        email=user_in.email,
        username=user_in.username,
    )
    _check_avatar(
        session=session,
        avatar_id=user_in.avatar_id,
        owner_id=current_user.id,
    )
    user_data = user_in.model_dump(exclude_unset=True)
    user = update_user_record(
        session=session,
        db_user=current_user,
        user_data=user_data,
    )
    session.commit()
    session.refresh(user)
    return user


def update_password_me(
    *, session: Session, current_user: User, body: UpdatePassword
) -> None:
    """修改当前用户密码"""
    verified, _ = verify_password(body.current_password, current_user.hashed_password)
    if not verified:
        raise HTTPException(status_code=400, detail="当前密码错误")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")
    current_user.hashed_password = get_password_hash(body.new_password)
    session.add(current_user)
    session.commit()


def _check_email_username_unique(
    *,
    session: Session,
    user_id: uuid.UUID | None,
    email: str | None,
    username: str | None,
) -> None:
    """校验邮箱 / 用户名是否被其他用户占用，冲突返回 409"""
    if email:
        existing_user = get_user_by_email(session=session, email=email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=409, detail="该邮箱已被其他用户使用")
    if username:
        existing_user = get_user_by_username(session=session, username=username)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(status_code=409, detail="该用户名已被其他用户使用")


def _check_avatar(
    *,
    session: Session,
    avatar_id: uuid.UUID | None,
    owner_id: uuid.UUID | None = None,
) -> None:
    """校验头像图片存在；用户本人设置时还需校验归属"""
    if avatar_id is None:
        return
    image = session.get(Image, avatar_id)
    if image is None:
        raise HTTPException(status_code=404, detail="头像图片不存在")
    if owner_id is not None and image.owner_id != owner_id:
        raise HTTPException(status_code=403, detail="无权使用该图片作为头像")


def _check_level(*, session: Session, level_id: uuid.UUID | None) -> None:
    """校验用户等级存在"""
    if level_id is None:
        return
    if session.get(UserLevel, level_id) is None:
        raise HTTPException(status_code=404, detail="用户等级不存在")
