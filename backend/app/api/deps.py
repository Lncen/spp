from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.init_models_data.permissions import is_registered_permission
from app.modules.auth.schemas import TokenPayload
from app.modules.authorization.application.permission_check import (
    has_any_permission,
    has_permission,
)
from app.modules.user.models import User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


def get_db() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无法验证凭据",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=403, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="权限不足"
        )
    return current_user


class PermissionChecker:
    """权限校验依赖：缺少权限时返回 403"""

    def __init__(self, code: str) -> None:
        self.code = code

    def check(self, *, session: SessionDep, current_user: CurrentUser) -> bool:
        """非抛出式判定，供「持有权限或资源归属本人」的接口使用"""
        return has_permission(
            session=session,
            user=current_user,
            code=self.code,
        )

    def __call__(
        self,
        session: SessionDep,
        current_user: CurrentUser,
    ) -> None:
        if not has_permission(
            session=session,
            user=current_user,
            code=self.code,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )


def require_permission(code: str) -> PermissionChecker:
    """声明接口所需权限码

    装饰器在模块导入期求值，因此未登记在权限清单里的权限码会直接导致启动失败。
    """
    if not is_registered_permission(code):
        raise RuntimeError(f"未登记的权限码：{code}")
    return PermissionChecker(code)


class AnyPermissionChecker:
    """权限校验依赖：持有任意一个权限码即通过

    缺失时按「业务性无权限」返回 400，而不是 403：
    403 表示 API 级权限码不足，会触发前端清登录态跳登录页，
    自助类接口（如会话自助能力）用 400 更合适。
    """

    def __init__(self, *codes: str, detail: str = "无访问权限") -> None:
        self.codes = codes
        self.detail = detail

    def __call__(
        self,
        session: SessionDep,
        current_user: CurrentUser,
    ) -> None:
        if not has_any_permission(session=session, user=current_user, codes=self.codes):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=self.detail,
            )


def require_any_permission(
    *codes: str, detail: str = "无访问权限"
) -> AnyPermissionChecker:
    """声明接口所需权限码之一（任一满足即可，缺失返回 400 业务性无权限）

    与 require_permission 一样在模块导入期校验权限码已登记。
    """
    for code in codes:
        if not is_registered_permission(code):
            raise RuntimeError(f"未登记的权限码：{code}")
    return AnyPermissionChecker(*codes, detail=detail)
