"""自动化模块：自动化任务手动重试应用服务"""

import uuid

from sqlalchemy.orm import Session

from app.modules.automation.models import AutomationTask
from app.modules.automation.repositories.task import (
    requeue_failed_task,
)


def retry_automation_task(
    *,
    session: Session,
    task_id: uuid.UUID,
) -> AutomationTask:
    """失败任务重新进入队列：任务池中直接重置，已归档则从归档表恢复。"""
    return requeue_failed_task(session=session, task_id=task_id)
