"""计划任务模块：路由层"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy_celery_beat.models import PeriodicTask
from sqlmodel import func, select

from app.api.deps import SessionDep, get_current_active_superuser
from app.common.models import Message
from app.modules.schedule.schemas import (
    RunTaskPublic,
    ScheduleCreate,
    SchedulePublic,
    SchedulesPublic,
    ScheduleUpdate,
    TaskOptionsPublic,
)
from app.modules.schedule.service import (
    _schedule_to_public,
    list_task_options,
    run_schedule_now,
)
from app.modules.schedule.service import (
    create_schedule as create_schedule_service,
)
from app.modules.schedule.service import (
    delete_schedule as delete_schedule_service,
)
from app.modules.schedule.service import (
    toggle_schedule as toggle_schedule_service,
)
from app.modules.schedule.service import (
    update_schedule as update_schedule_service,
)

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _get_task_or_404(session: Session, task_id: int) -> PeriodicTask:
    """按 ID 获取计划任务，不存在时返回 404。"""
    task = session.get(PeriodicTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="计划任务不存在")
    return task


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
    count = session.exec(select(func.count()).select_from(PeriodicTask)).one()
    tasks = session.exec(
        select(PeriodicTask).order_by(PeriodicTask.id).offset(skip).limit(limit)
    ).all()
    return SchedulesPublic(
        data=[_schedule_to_public(task) for task in tasks],
        count=count,
    )


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
    return _schedule_to_public(_get_task_or_404(session, id))


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
    return _schedule_to_public(task)


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
    task = _get_task_or_404(session, id)
    try:
        task = update_schedule_service(
            session=session,
            task=task,
            schedule_in=schedule_in,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return _schedule_to_public(task)


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
    task = _get_task_or_404(session, id)
    return _schedule_to_public(
        toggle_schedule_service(session=session, task=task)
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
    task = _get_task_or_404(session, id)
    return RunTaskPublic(task_id=run_schedule_now(task))


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
    delete_schedule_service(session=session, task=_get_task_or_404(session, id))
    return Message(message="计划任务已删除")
