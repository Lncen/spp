"""公共路由：健康检查和工具接口"""

from fastapi import APIRouter, Depends
from pydantic.networks import EmailStr

from app.api.deps import require_permission
from app.common.models import Message
from app.utils import generate_test_email, send_email

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post(
    "/test-email/",
    dependencies=[Depends(require_permission("system:test_email"))],
    status_code=201,
)
def test_email(email_to: EmailStr) -> Message:
    """发送测试邮件"""
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="测试邮件已发送")


@router.get("/health-check/")
async def health_check() -> bool:
    """健康检查"""
    return True
