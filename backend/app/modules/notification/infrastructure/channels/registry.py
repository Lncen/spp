"""通知渠道注册表（独立文件，不依赖 __init__.py 副作用）"""

from collections.abc import Callable

from app.modules.notification.infrastructure.channels.base import (
    BaseChannel,
    NotificationChannelError,
)

CHANNELS: dict[str, type[BaseChannel]] = {}


def register_channel(
    name: str,
) -> Callable[[type[BaseChannel]], type[BaseChannel]]:
    """类装饰器：将渠道类注册到渠道名映射"""

    def decorator(cls: type[BaseChannel]) -> type[BaseChannel]:
        CHANNELS[name] = cls
        return cls

    return decorator


def get_channel(name: str) -> BaseChannel:
    """按渠道名获取渠道实例，未注册时抛出明确错误"""
    try:
        return CHANNELS[name]()
    except KeyError as e:
        raise NotificationChannelError(f"未注册的通知渠道: {name}") from e
