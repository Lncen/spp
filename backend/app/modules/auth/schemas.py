"""认证模块：API 请求与响应模型"""
from sqlmodel import Field, SQLModel


class Token(SQLModel):
    """访问令牌响应"""
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    """JWT 令牌载荷"""
    sub: str | None = None


class NewPassword(SQLModel):
    """重置密码请求"""
    token: str
    new_password: str = Field(min_length=8, max_length=128)
