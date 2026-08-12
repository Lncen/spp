"""自动化模块：自动化规则数据模型"""

from typing import Any

from sqlalchemy import JSON
from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin


class AutomationRule(BaseModelMixin, SQLModel, table=True):
    """自动化规则：事件类型 → 动作类型，事件到达时生成对应自动化任务"""

    __tablename__ = "automation_rules"

    name: str = Field(
        max_length=128,
        nullable=False,
        title="规则名称",
        description="规则的业务名称，便于管理与前端展示",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        title="规则描述",
        description="规则用途说明",
    )
    event_type: str = Field(
        max_length=64,
        index=True,
        nullable=False,
        title="事件类型",
        description="监听的事件类型，如 order.paid",
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
    priority: int = Field(
        default=0,
        index=True,
        title="规则优先级",
        description="数值越大越优先匹配/生成任务",
    )
