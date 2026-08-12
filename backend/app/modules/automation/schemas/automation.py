"""自动化模块：任务池 API 请求与响应模型"""

import uuid
from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel

from app.modules.automation.domain.constants import (
    AutomationEventStatus,
    AutomationTaskStatus,
)


class AutomationTaskCreate(SQLModel):
    """创建自动化任务请求"""

    task_type: str = Field(
        min_length=1,
        max_length=64,
        title="任务类型",
        description="对应已注册 Executor 的任务类型",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        title="任务参数",
        description="执行所需参数",
    )
    priority: int = Field(
        default=0,
        title="优先级",
        description="数值越大越优先执行",
    )
    execute_at: datetime | None = Field(
        default=None,
        title="计划执行时间",
        description="为空则立即执行",
    )
    max_retry: int = Field(
        default=3,
        ge=0,
        le=10,
        title="最大重试次数",
    )


class AutomationTaskPublic(SQLModel):
    """自动化任务公开响应"""

    id: uuid.UUID
    task_type: str
    event_id: uuid.UUID | None
    rule_id: uuid.UUID | None
    event_type_label: str | None = Field(
        default=None,
        title="来源事件类型（中文展示名）",
        description="生成该任务的事件类型中文名，未知类型回退原始事件类型；手动创建任务时为空",
    )
    rule_name: str | None = Field(
        default=None,
        title="来源规则名称",
        description="生成该任务的 AutomationRule.name，手动创建任务时为空",
    )
    status: AutomationTaskStatus
    priority: int
    execute_at: datetime
    retry_count: int
    max_retry: int
    payload: dict[str, Any]
    last_error: str | None
    claimed_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class AutomationTasksPublic(SQLModel):
    """自动化任务列表响应"""

    data: list[AutomationTaskPublic]
    count: int


class AutomationTaskArchivePublic(SQLModel):
    """自动化任务归档公开响应"""

    id: uuid.UUID
    task_id: uuid.UUID
    task_type: str
    event_id: uuid.UUID | None
    rule_id: uuid.UUID | None
    event_type_label: str | None = Field(
        default=None,
        title="来源事件类型（中文展示名）",
        description="生成该任务的事件类型中文名，未知类型回退原始事件类型；手动创建任务时为空",
    )
    rule_name: str | None = Field(
        default=None,
        title="来源规则名称",
        description="生成该任务的 AutomationRule.name，手动创建任务时为空",
    )
    status: AutomationTaskStatus
    priority: int
    execute_at: datetime
    retry_count: int
    max_retry: int
    payload: dict[str, Any]
    last_error: str | None
    claimed_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime | None
    archived_at: datetime


class AutomationTaskArchivesPublic(SQLModel):
    """自动化任务归档列表响应"""

    data: list[AutomationTaskArchivePublic]
    count: int


class AutomationEventCreate(SQLModel):
    """发布业务事件请求"""

    event_type: str = Field(
        min_length=1,
        max_length=64,
        title="事件类型",
        description="如 order.paid",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        title="事件载荷",
    )


class AutomationEventPublic(SQLModel):
    """自动化事件公开响应"""

    id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    status: AutomationEventStatus
    dispatch_attempts: int
    last_error: str | None
    next_dispatch_at: datetime | None
    processing_at: datetime | None
    dispatched_at: datetime | None
    created_at: datetime | None


class AutomationEventsPublic(SQLModel):
    """自动化事件列表响应"""

    data: list[AutomationEventPublic]
    count: int


class AutomationRuleCreate(SQLModel):
    """创建自动化规则请求"""

    name: str = Field(
        min_length=1,
        max_length=128,
        title="规则名称",
        description="规则的业务名称",
    )
    description: str | None = Field(
        default=None,
        max_length=500,
        title="规则描述",
    )
    event_type: str = Field(
        min_length=1,
        max_length=64,
        title="事件类型",
        description="监听的业务事件类型",
    )
    action_type: str = Field(
        min_length=1,
        max_length=64,
        title="动作类型",
        description="对应已注册 Executor 的任务类型",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        title="规则配置",
        description="合并进任务 payload，可覆盖事件载荷中的同名参数",
    )
    priority: int = Field(
        default=0,
        title="规则优先级",
        description="数值越大越优先匹配/生成任务",
    )
    is_active: bool = Field(default=True, title="是否启用")


class AutomationRuleUpdate(SQLModel):
    """更新自动化规则请求（全部可选）"""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=500)
    event_type: str | None = Field(default=None, min_length=1, max_length=64)
    action_type: str | None = Field(default=None, min_length=1, max_length=64)
    config: dict[str, Any] | None = None
    priority: int | None = None
    is_active: bool | None = None


class AutomationRulePublic(SQLModel):
    """自动化规则公开响应"""

    id: uuid.UUID
    name: str
    description: str | None
    event_type: str
    action_type: str
    config: dict[str, Any]
    priority: int
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None


class AutomationRulesPublic(SQLModel):
    """自动化规则列表响应"""

    data: list[AutomationRulePublic]
    count: int
