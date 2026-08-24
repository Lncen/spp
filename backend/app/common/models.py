"""公共模型与工具函数"""
from sqlmodel import SQLModel


class Message(SQLModel):
    """通用响应消息"""
    message: str
