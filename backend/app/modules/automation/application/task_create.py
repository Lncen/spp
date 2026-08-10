"""自动化模块：创建自动化任务应用服务"""

from sqlalchemy.orm import Session

from app.modules.automation.infrastructure.executors import get_executor
from app.modules.automation.models import AutomationTask
from app.modules.automation.repositories.task import (
    create_task as create_task_record,
)
from app.modules.automation.schemas import AutomationTaskCreate


def create_automation_task(
    *,
    session: Session,
    task_in: AutomationTaskCreate,
) -> AutomationTask:
    """创建自动化任务，任务类型必须已注册 Executor，否则抛出 ValueError。"""
    get_executor(task_in.task_type)
    task = create_task_record(
        session=session,
        task_type=task_in.task_type,
        payload=task_in.payload,
        priority=task_in.priority,
        execute_at=task_in.execute_at,
        max_retry=task_in.max_retry,
    )
    session.commit()
    session.refresh(task)
    return task
