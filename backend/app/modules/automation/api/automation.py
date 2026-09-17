"""自动化模块：任务池路由"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import SessionDep, get_current_active_superuser
from app.modules.automation.application.task import (
    cancel_automation_task as cancel_automation_task_service,
)
from app.modules.automation.application.task import (
    create_automation_task as create_automation_task_service,
)
from app.modules.automation.application.task import (
    get_automation_task_public,
    list_automation_task_archives,
    list_automation_tasks,
    list_executor_options,
    to_automation_task_public,
)
from app.modules.automation.application.task import (
    retry_automation_task as retry_automation_task_service,
)
from app.modules.automation.domain.constants import AutomationTaskStatus
from app.modules.automation.schemas import (
    AutomationTaskArchivesPublic,
    AutomationTaskCreate,
    AutomationTaskPublic,
    AutomationTasksPublic,
    TaskOptionsPublic,
)

router = APIRouter(prefix="/automation/tasks", tags=["automation"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AutomationTasksPublic,
)
def read_automation_tasks(
    session: SessionDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    status: AutomationTaskStatus | None = Query(
        default=None,
        title="任务状态过滤",
    ),
) -> Any:
    """获取自动化任务列表（超管权限）"""
    return list_automation_tasks(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
    )


@router.get(
    "/task-options",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TaskOptionsPublic,
)
def read_executor_options() -> Any:
    """获取已注册 Executor 任务类型列表（超管权限，前端下拉使用）"""
    return TaskOptionsPublic(data=list_executor_options())


@router.get(
    "/archive",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AutomationTaskArchivesPublic,
)
def read_automation_task_archives(
    session: SessionDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    status: AutomationTaskStatus | None = Query(
        default=None,
        title="任务状态过滤",
    ),
) -> Any:
    """获取自动化任务归档列表（超管权限）"""
    return list_automation_task_archives(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
    )


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AutomationTaskPublic,
)
def create_automation_task(
    *,
    session: SessionDep,
    task_in: AutomationTaskCreate,
) -> Any:
    """创建自动化任务（超管权限）"""
    try:
        task = create_automation_task_service(session=session, task_in=task_in)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return to_automation_task_public(task)


@router.get(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AutomationTaskPublic,
)
def read_automation_task(
    session: SessionDep,
    id: uuid.UUID,
) -> Any:
    """根据 ID 获取自动化任务（超管权限）"""
    return get_automation_task_public(session=session, task_id=id)


@router.post(
    "/{id}/retry",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AutomationTaskPublic,
)
def retry_automation_task(
    session: SessionDep,
    id: uuid.UUID,
) -> Any:
    """手动重试失败任务（超管权限）"""
    try:
        task = retry_automation_task_service(session=session, task_id=id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return to_automation_task_public(task)


@router.post(
    "/{id}/cancel",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AutomationTaskPublic,
)
def cancel_automation_task(
    session: SessionDep,
    id: uuid.UUID,
) -> Any:
    """取消待执行任务（超管权限）"""
    try:
        task = cancel_automation_task_service(session=session, task_id=id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return to_automation_task_public(task)
