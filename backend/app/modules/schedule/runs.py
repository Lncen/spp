"""计划任务模块：失败执行记录路由"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, get_current_active_superuser
from app.modules.schedule.schemas import ScheduleRunPublic, ScheduleRunsPublic
from app.modules.schedule.service import list_failed_runs

router = APIRouter(prefix="/schedules/runs", tags=["schedules"])


@router.get(
    "/failed",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ScheduleRunsPublic,
)
def read_failed_runs(
    session: SessionDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    task_name: str | None = Query(default=None, title="任务名称过滤"),
) -> Any:
    """获取计划任务失败执行记录（超管权限）"""
    runs, count = list_failed_runs(
        session=session,
        skip=skip,
        limit=limit,
        task_name=task_name,
    )
    return ScheduleRunsPublic(
        data=[ScheduleRunPublic.model_validate(run) for run in runs],
        count=count,
    )
