"""自动化模块：Celery 任务状态应用服务"""

from app.modules.automation.infrastructure.celery import fetch_task_status
from app.modules.automation.schemas import TaskStatusPublic


def get_task_status(task_id: str) -> TaskStatusPublic:
    """查询 Celery 任务执行状态。"""
    return fetch_task_status(task_id)
