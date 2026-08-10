"""自动化模块：任务选项应用服务"""

from app.modules.automation.infrastructure.celery import (
    list_task_options as list_celery_task_options,
)
from app.modules.automation.schemas import TaskOption


def list_task_options() -> list[TaskOption]:
    """列出可配置的 Celery 任务。"""
    return list_celery_task_options()
