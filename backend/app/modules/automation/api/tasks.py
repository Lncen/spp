"""自动化模块：任务状态路由"""

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import require_permission
from app.modules.automation.application.schedule import get_task_status
from app.modules.automation.schemas import TaskStatusPublic

router = APIRouter(prefix="/schedules/tasks", tags=["schedules"])


@router.get(
    "/{task_id}/status",
    dependencies=[Depends(require_permission("schedule:view"))],
    response_model=TaskStatusPublic,
)
def read_task_status(task_id: str) -> Any:
    """查询 Celery 任务执行状态"""
    return get_task_status(task_id)
