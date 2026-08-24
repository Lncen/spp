"""操作审计数据模型：记录谁对什么数据做了什么操作"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime
from sqlmodel import Field, SQLModel

from app.core.mixin.models import UUIDPrimaryKeyMixin
from app.core.time import get_datetime_cn


class AuditLog(UUIDPrimaryKeyMixin, SQLModel, table=True):
    """操作审计：不可轻易修改、不可轻易删除的历史事实"""

    __tablename__ = "audit_logs"

    actor_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        ondelete="SET NULL",
        index=True,
        title="操作者 ID",
        description="操作者用户 ID；用户删除后置空，保留标识快照",
    )
    actor_identifier: str | None = Field(
        default=None,
        max_length=255,
        title="操作者标识快照",
        description="操作者邮箱或用户名快照，防止用户删除后审计链断裂",
    )
    action: str = Field(
        max_length=128,
        index=True,
        nullable=False,
        title="操作类型",
        description="如 order.update_status / wallet.adjust / order.refund",
    )
    resource_type: str = Field(
        max_length=64,
        index=True,
        nullable=False,
        title="目标对象类型",
        description="如 order / wallet / product / user",
    )
    resource_id: str | None = Field(
        default=None,
        max_length=128,
        index=True,
        title="目标对象 ID",
        description="被操作业务资源的 ID 字符串快照",
    )
    before: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        title="操作前状态",
        description="仅记录与本次操作相关的关键字段",
    )
    after: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        title="操作后状态",
        description="仅记录与本次操作相关的关键字段",
    )
    changes: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        title="变更字段",
        description="按字段记录 old -> new 的结构化变更",
    )
    ip: str | None = Field(
        default=None,
        max_length=64,
        title="来源 IP",
        description="操作发起方 IP 地址",
    )
    user_agent: str | None = Field(
        default=None,
        max_length=512,
        title="User-Agent",
        description="操作发起方 User-Agent 快照",
    )
    request_id: str | None = Field(
        default=None,
        max_length=128,
        index=True,
        title="请求 ID",
        description="产生该操作的 HTTP 请求 ID",
    )
    event_id: uuid.UUID | None = Field(
        default=None,
        index=True,
        title="来源事件 ID",
        description="如由事件间接触发，可关联 AutomationEvent ID",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_cn,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
        index=True,
        nullable=False,
        title="操作时间",
        description="审计记录落库时间（北京时间）",
    )
