"""公共模型与工具函数"""
from datetime import UTC, datetime

from sqlmodel import SQLModel


def get_datetime_utc() -> datetime:
    """获取当前 UTC 时间"""
    return datetime.now(UTC)


class Message(SQLModel):
    """通用响应消息"""
    message: str
