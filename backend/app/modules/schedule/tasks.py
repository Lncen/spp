"""计划任务模块：任务状态路由"""

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import get_current_active_superuser
from app.modules.schedule.schemas import TaskStatusPublic
from app.modules.schedule.service import get_task_status

router = APIRouter(prefix="/schedules/tasks", tags=["schedules"])


@router.get(
    "/{task_id}/status",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TaskStatusPublic,
)
def read_task_status(task_id: str) -> Any:
    """查询 Celery 任务执行状态（超管权限）"""
    return get_task_status(task_id)
