"""自动化模块：路由层"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import SessionDep, get_current_active_superuser
from app.common.models import Message
from app.modules.automation.application.schedule_create import (
    create_schedule as create_schedule_service,
)
from app.modules.automation.application.schedule_delete import (
    delete_schedule as delete_schedule_service,
)
from app.modules.automation.application.schedule_query import (
    get_schedule_public,
    list_schedules,
    to_schedule_public,
)
from app.modules.automation.application.schedule_run import run_schedule_now
from app.modules.automation.application.schedule_toggle import (
    toggle_schedule as toggle_schedule_service,
)
from app.modules.automation.application.schedule_update import (
    update_schedule as update_schedule_service,
)
from app.modules.automation.application.task_options import list_task_options
from app.modules.automation.schemas import (
    RunTaskPublic,
    ScheduleCreate,
    SchedulePublic,
    SchedulesPublic,
    ScheduleUpdate,
    TaskOptionsPublic,
)

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SchedulesPublic,
)
def read_schedules(
    session: SessionDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> Any:
    """获取计划任务列表（超管权限）"""
    return list_schedules(session=session, skip=skip, limit=limit)


@router.get(
    "/task-options",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TaskOptionsPublic,
)
def read_task_options() -> Any:
    """获取可配置的 Celery 任务列表（超管权限，前端下拉使用）"""
    return TaskOptionsPublic(data=list_task_options())


@router.get(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SchedulePublic,
)
def read_schedule(
    session: SessionDep,
    id: int,
) -> Any:
    """根据 ID 获取计划任务（超管权限）"""
    return get_schedule_public(session=session, task_id=id)


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SchedulePublic,
)
def create_schedule(
    *,
    session: SessionDep,
    schedule_in: ScheduleCreate,
) -> Any:
    """创建计划任务（超管权限）"""
    try:
        task = create_schedule_service(session=session, schedule_in=schedule_in)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return to_schedule_public(task)


@router.put(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SchedulePublic,
)
def update_schedule(
    *,
    session: SessionDep,
    id: int,
    schedule_in: ScheduleUpdate,
) -> Any:
    """更新计划任务（超管权限）"""
    try:
        task = update_schedule_service(
            session=session,
            task_id=id,
            schedule_in=schedule_in,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return to_schedule_public(task)


@router.post(
    "/{id}/toggle",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SchedulePublic,
)
def toggle_schedule(
    session: SessionDep,
    id: int,
) -> Any:
    """启用或停用计划任务（超管权限）"""
    return to_schedule_public(
        toggle_schedule_service(session=session, task_id=id)
    )


@router.post(
    "/{id}/run",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=RunTaskPublic,
)
def run_schedule(
    session: SessionDep,
    id: int,
) -> Any:
    """立即执行一次计划任务（超管权限，不影响原计划）"""
    return RunTaskPublic(task_id=run_schedule_now(session=session, task_id=id))


@router.delete(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def delete_schedule(
    session: SessionDep,
    id: int,
) -> Message:
    """删除计划任务（超管权限）"""
    delete_schedule_service(session=session, task_id=id)
    return Message(message="计划任务已删除")
