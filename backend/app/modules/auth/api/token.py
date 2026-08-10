"""认证模块：令牌校验相关路由"""

from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.modules.user.schemas import UserPublic

router = APIRouter(tags=["login"])


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """测试访问令牌是否有效"""
    return current_user
