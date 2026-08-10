"""认证模块：登录相关路由（登录、刷新令牌、登出）"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import SessionDep
from app.common.models import Message
from app.core import security
from app.core.config import settings
from app.modules.auth.schemas import RefreshTokenRequest, Token
from app.modules.auth.service import (
    authenticate,
    clear_login_failures,
    is_login_locked,
    issue_refresh_token,
    record_login_failure,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
def login_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """OAuth2 兼容的登录接口，获取访问令牌与刷新令牌"""
    login = form_data.username
    if is_login_locked(session=session, login=login):
        raise HTTPException(status_code=429, detail="登录失败次数过多，请稍后再试")
    user = authenticate(
        session=session, login=login, password=form_data.password
    )
    if not user:
        record_login_failure(session=session, login=login)
        raise HTTPException(status_code=400, detail="邮箱或密码错误")
    elif not user.is_active:
        clear_login_failures(login)
        raise HTTPException(status_code=400, detail="用户已被禁用")
    clear_login_failures(login)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token = issue_refresh_token(session=session, user=user)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        refresh_token=refresh_token,
    )


@router.post("/login/refresh-token")
def refresh_token(session: SessionDep, body: RefreshTokenRequest) -> Token:
    """使用刷新令牌换取新的访问令牌，旧刷新令牌立即作废（旋转）"""
    rotated = rotate_refresh_token(session=session, token=body.refresh_token)
    if rotated is None:
        raise HTTPException(status_code=401, detail="刷新令牌无效或已过期")
    new_refresh_token, user = rotated
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        refresh_token=new_refresh_token,
    )


@router.post("/login/logout")
def logout(session: SessionDep, body: RefreshTokenRequest) -> Message:
    """登出：撤销刷新令牌，使其无法再刷新"""
    revoke_refresh_token(session=session, token=body.refresh_token)
    return Message(message="退出成功")
