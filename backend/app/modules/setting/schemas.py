"""全局设置模块：API 请求与响应模型"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlmodel import SQLModel


class SettingRead(SQLModel):
    """设置项（登录用户可读）"""

    key: str
    value: Any
    description: str | None
    updated_by: UUID | None
    updated_at: datetime | None


class SettingsRead(SQLModel):
    """设置列表响应"""

    data: list[SettingRead]


class SettingUpdate(SQLModel):
    """更新设置请求"""

    value: Any
