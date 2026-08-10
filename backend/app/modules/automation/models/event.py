"""AutomationEvent 数据模型：业务事件"""

from typing import Any

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin


class AutomationEvent(BaseModelMixin, SQLModel, table=True):
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
