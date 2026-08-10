"""自动化模块：立即执行计划任务应用服务"""

import json

from sqlalchemy.orm import Session

from app.modules.automation.infrastructure.celery import send_task_now
from app.modules.automation.repositories.schedule import get_task_or_404


def run_schedule_now(*, session: Session, task_id: int) -> str:
    """立即发送一次任务，不改变原计划。"""
    task = get_task_or_404(session=session, task_id=task_id)
    args = json.loads(task.args or "[]")
    kwargs = json.loads(task.kwargs or "{}")
    return send_task_now(task_name=task.task, args=args, kwargs=kwargs)
