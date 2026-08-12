"""自动化模块：业务事件数据模型"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlmodel import Field, SQLModel

from app.core.mixin.models import UUIDPrimaryKeyMixin, get_datetime_utc
from app.modules.automation.domain.constants import AutomationEventStatus


class AutomationEvent(UUIDPrimaryKeyMixin, SQLModel, table=True):
    """业务事件：由业务模块发布，供自动化规则消费"""

    __tablename__ = "automation_events"

    event_type: str = Field(
        max_length=64,
        index=True,
        nullable=False,
        title="事件类型",
        description="如 order.paid、product.stock_low",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        title="事件载荷",
        description="事件携带的业务参数，JSON 存储",
    )
    status: AutomationEventStatus = Field(
        default=AutomationEventStatus.PENDING,
        sa_type=String(20),
        index=True,
        nullable=False,
        title="事件状态",
        description="pending=待分发 / dispatching=分发中 / dispatched=已分发 / failed=分发失败",
    )
    dispatch_attempts: int = Field(
        default=0,
        nullable=False,
        title="分发次数",
        description="累计分发尝试次数，失败补发时递增",
    )
    last_error: str | None = Field(
        default=None,
        max_length=2000,
        title="最近错误",
        description="最近一次分发失败原因",
    )
    next_dispatch_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        index=True,
        title="下次分发时间",
        description="分发失败后的计划补发时间（UTC），暂由补发机制使用",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
        nullable=False,
        title="创建时间",
        description="事件落库时间（UTC）",
    )
    processing_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        title="处理时间",
        description="开始分发的时刻（UTC）",
    )
    dispatched_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        title="分发完成时间",
        description="分发完成的时刻（UTC）",
    )
