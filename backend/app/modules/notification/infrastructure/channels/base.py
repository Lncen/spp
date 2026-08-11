"""通知渠道：抽象基类与异常"""

from abc import ABC, abstractmethod

from sqlmodel import Session

from app.modules.notification.models import Notification, NotificationDelivery


class NotificationChannelError(Exception):
    """渠道投递失败（可重试），由 Celery 任务捕获后按策略重试"""


class BaseChannel(ABC):
    """渠道抽象：子类实现 send，并通过 register_channel 注册"""

    @abstractmethod
    def send(
        self,
        *,
        delivery: NotificationDelivery,
        notification: Notification,
        session: Session,
    ) -> None:
        """执行一次渠道投递，失败时抛出异常交由任务重试"""
