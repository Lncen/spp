"""认证模块：密码相关路由（找回、重置）"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.api.deps import SessionDep, require_permission
from app.common.models import Message
from app.modules.auth.schemas import NewPassword
from app.modules.user.application.user_query import get_user_by_email
from app.modules.user.application.user_update import update_user
from app.modules.user.schemas import UserUpdate
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

router = APIRouter(tags=["login"])


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
    dependencies=[Depends(require_permission("user:view"))],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """获取密码找回邮件的 HTML 内容（需 `user:view`）"""
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
