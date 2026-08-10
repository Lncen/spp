"""自动化模块：自动化任务取消应用服务"""

import uuid

from sqlalchemy.orm import Session

from app.modules.automation.models import AutomationTask
from app.modules.automation.repositories.task import (
    cancel_task,
    get_task_or_404,
)


def cancel_automation_task(
    *,
    session: Session,
    task_id: uuid.UUID,
) -> AutomationTask:
    """取消待执行任务，非待执行状态时抛出 ValueError。"""
    task = get_task_or_404(session=session, task_id=task_id)
    cancel_task(session=session, task=task)
    return task
