"""用户模块：内部管理路由（原 private.py，仅 local 环境注册）"""

from typing import Any

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.modules.user.application.user_create import (
    create_user_private as create_user_private_service,
)
from app.modules.user.schemas import PrivateUserCreate, UserPublic

private_router = APIRouter(prefix="/private", tags=["private"])


@private_router.post("/users/", response_model=UserPublic)
def create_user_private(user_in: PrivateUserCreate, session: SessionDep) -> Any:
    """内部接口：创建新用户（仅开发环境可用）"""
    return create_user_private_service(session=session, user_in=user_in)
