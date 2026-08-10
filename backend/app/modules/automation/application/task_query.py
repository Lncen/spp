"""自动化模块：自动化任务查询应用服务"""

import uuid

from sqlalchemy.orm import Session

from app.modules.automation.domain.constants import AutomationTaskStatus
from app.modules.automation.models import AutomationTask
from app.modules.automation.repositories.task import (
    count_tasks,
    get_task_or_404,
    list_tasks,
)
from app.modules.automation.schemas import (
    AutomationTaskPublic,
    AutomationTasksPublic,
)

__all__ = [
    "get_automation_task_public",
    "list_automation_tasks",
    "to_automation_task_public",
]


def list_automation_tasks(
    *,
    session: Session,
    skip: int,
    limit: int,
    status: AutomationTaskStatus | None,
) -> AutomationTasksPublic:
    """分页获取自动化任务列表。"""
    count = count_tasks(session=session, status=status)
    tasks = list_tasks(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
    )
    return AutomationTasksPublic(
        data=[to_automation_task_public(task) for task in tasks],
        count=count,
    )


def get_automation_task_public(
    *,
    session: Session,
    task_id: uuid.UUID,
) -> AutomationTaskPublic:
    """按 ID 获取自动化任务公开响应。"""
    return to_automation_task_public(
        get_task_or_404(session=session, task_id=task_id)
    )


def to_automation_task_public(task: AutomationTask) -> AutomationTaskPublic:
    """将 AutomationTask 转为公开响应模型。"""
    return AutomationTaskPublic.model_validate(task)
