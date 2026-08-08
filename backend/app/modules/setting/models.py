"""全局设置模块：数据库模型"""

from typing import Any

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

from app.core.mixin.models import AuditUserMixin, BaseModelMixin


class AppSetting(BaseModelMixin, AuditUserMixin, SQLModel, table=True):
    """全局设置项（运行时可控，key-value 结构）"""

    __tablename__ = "app_setting"

    key: str = Field(
        unique=True,
        index=True,
        max_length=100,
        nullable=False,
        title="设置键",
        description="全局唯一，如 maintenance_mode、order_enabled",
    )
    value: Any = Field(
        default=None,
        sa_type=JSON,
        title="设置值",
        description="任意 JSON 值，支持 bool/str/int/list/dict",
    )
    description: str | None = Field(
        default=None,
        max_length=255,
        title="设置说明",
        description="开关用途说明，供管理界面展示",
    )
