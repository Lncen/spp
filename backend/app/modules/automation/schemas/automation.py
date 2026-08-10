"""自动化模块：任务池 API 请求与响应模型"""

import uuid
from datetime import datetime
from typing import Any

from sqlmodel import Field, SQLModel

from app.modules.automation.domain.constants import AutomationTaskStatus


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
    status: AutomationTaskStatus
    priority: int
    execute_at: datetime
    retry_count: int
    max_retry: int
    payload: dict[str, Any]
    error_message: str | None
    finished_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class AutomationTasksPublic(SQLModel):
    """自动化任务列表响应"""

    data: list[AutomationTaskPublic]
    count: int


class AutomationTaskArchivePublic(AutomationTaskPublic):
    """自动化任务归档公开响应"""

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
    created_at: datetime | None


class AutomationEventsPublic(SQLModel):
    """自动化事件列表响应"""

    data: list[AutomationEventPublic]
    count: int


class AutomationRuleCreate(SQLModel):
    """创建自动化规则请求"""

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
    is_active: bool = Field(default=True, title="是否启用")


class AutomationRuleUpdate(SQLModel):
    """更新自动化规则请求（全部可选）"""

    event_type: str | None = Field(default=None, min_length=1, max_length=64)
    action_type: str | None = Field(default=None, min_length=1, max_length=64)
    config: dict[str, Any] | None = None
    is_active: bool | None = None


class AutomationRulePublic(SQLModel):
    """自动化规则公开响应"""

    id: uuid.UUID
    event_type: str
    action_type: str
    config: dict[str, Any]
    is_active: bool
    created_at: datetime | None
    updated_at: datetime | None


class AutomationRulesPublic(SQLModel):
    """自动化规则列表响应"""

    data: list[AutomationRulePublic]
    count: int
