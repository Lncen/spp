"""AutomationRule 数据模型：自动化规则"""

from typing import Any

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin


class AutomationRule(BaseModelMixin, SQLModel, table=True):
    """自动化规则：事件类型 → 动作类型，事件到达时生成对应自动化任务"""

    __tablename__ = "automation_rules"

    event_type: str = Field(
        max_length=64,
        index=True,
        nullable=False,
        title="事件类型",
        description="监听的业务事件类型",
    )
    action_type: str = Field(
        max_length=64,
        index=True,
        nullable=False,
        title="动作类型",
        description="对应已注册 Executor 的任务类型",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        sa_type=JSON,
        title="规则配置",
        description="合并进任务 payload，可覆盖事件载荷中的同名参数",
    )
