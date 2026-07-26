"""认证模块：路由层。函数名保持不变以保证 OpenAPI operationId 兼容性"""

from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.common.models import Message
from app.core import security
from app.core.config import settings
from app.modules.auth.schemas import NewPassword, Token
from app.modules.auth.service import authenticate
from app.modules.user.schemas import UserPublic, UserUpdate
from app.modules.user.service import get_user_by_email, update_user
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
def login_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """OAuth2 兼容的登录接口，获取访问令牌"""
    user = authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(status_code=400, detail="邮箱或密码错误")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """测试访问令牌是否有效"""
    return current_user


@router.post("/password-recovery/{email}")
def recover_password(email: str, session: SessionDep) -> Message:
    """密码找回——发送重置链接邮件"""
    user = get_user_by_email(session=session, email=email)

    # 无论邮箱是否存在都返回相同响应，防止邮箱枚举攻击
    if user:
        password_reset_token = generate_password_reset_token(email=email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return Message(message="如果该邮箱已注册，我们将发送密码重置链接")


@router.post("/reset-password/")
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    """重置密码"""
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="无效的令牌")
    user = get_user_by_email(session=session, email=email)
    if not user:
        # 不泄露用户不存在的信息——和无效令牌使用相同错误提示
        raise HTTPException(status_code=400, detail="无效的令牌")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="用户已被禁用")
    user_in_update = UserUpdate(password=body.new_password)
    update_user(session=session, db_user=user, user_in=user_in_update)
    return Message(message="密码重置成功")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """获取密码找回邮件的 HTML 内容（仅超级管理员可用）"""
    user = get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="系统中不存在该用户",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
