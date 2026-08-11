"""通知渠道：邮件（email），复用全局 SMTP 发送能力与模块内模板"""

import logging

from sqlmodel import Session

from app.core.config import settings
from app.modules.notification.domain.constants import ChannelType
from app.modules.notification.infrastructure.channels.base import (
    BaseChannel,
    NotificationChannelError,
)
from app.modules.notification.infrastructure.channels.registry import register_channel
from app.modules.notification.models import Notification, NotificationDelivery
from app.utils import render_email_template, send_email

logger = logging.getLogger(__name__)


@register_channel(ChannelType.EMAIL)
class EmailChannel(BaseChannel):
    """邮件渠道：按通知记录的模板与载荷渲染 HTML 并发送"""

    def send(
        self,
        *,
        delivery: NotificationDelivery,
        notification: Notification,
        session: Session,
    ) -> None:
        if not settings.emails_enabled:
            raise NotificationChannelError("SMTP 未配置，邮件渠道不可用")
        if not notification.email_to:
            raise NotificationChannelError("邮件渠道缺少接收邮箱 email_to")
        if not notification.template_name:
            raise NotificationChannelError("邮件渠道缺少模板 template_name")
        context = {
            "project_name": settings.PROJECT_NAME,
            **notification.payload_snapshot,
        }
        html_content = render_email_template(
            template_name=notification.template_name,
            context=context,
        )
        send_email(
            email_to=notification.email_to,
            subject=notification.title,
            html_content=html_content,
        )
