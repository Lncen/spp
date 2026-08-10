"""用户模块：邮件通知基础设施"""

from app.core.config import settings
from app.utils import generate_new_account_email, send_email


def send_new_account_email(*, email: str, password: str) -> None:
    """创建账号后发送通知邮件（邮件功能未启用时静默跳过）"""
    if not settings.emails_enabled or not email:
        return
    email_data = generate_new_account_email(
        email_to=email,
        username=email,
        password=password,
    )
    send_email(
        email_to=email,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
