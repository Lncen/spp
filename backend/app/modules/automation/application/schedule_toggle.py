"""自动化模块：启用/停用计划任务应用服务"""

from sqlalchemy.orm import Session
from sqlalchemy_celery_beat.models import PeriodicTask

from app.modules.automation.repositories.schedule import get_task_or_404


def toggle_schedule(*, session: Session, task_id: int) -> PeriodicTask:
    """启用或停用计划任务。"""
    task = get_task_or_404(session=session, task_id=task_id)
    task.enabled = not task.enabled
    session.add(task)
    session.commit()
    session.refresh(task)
    return task
