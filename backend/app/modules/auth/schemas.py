"""认证模块：API 请求与响应模型"""
from sqlmodel import Field, SQLModel


class Token(SQLModel):
    """访问令牌响应（登录与刷新时返回）"""
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None


class RefreshTokenRequest(SQLModel):
    """刷新令牌请求"""
    refresh_token: str = Field(min_length=1)


class TokenPayload(SQLModel):
    """JWT 令牌载荷"""
    sub: str | None = None


class NewPassword(SQLModel):
    """重置密码请求"""
    token: str
    new_password: str = Field(min_length=8, max_length=128)
