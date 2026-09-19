"""自动化模块：任务池路由"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import SessionDep, require_permission
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
    dependencies=[Depends(require_permission("automation_task:view"))],
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
    """获取自动化任务列表"""
    return list_automation_tasks(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
    )


@router.get(
    "/task-options",
    dependencies=[Depends(require_permission("automation_task:view"))],
    response_model=TaskOptionsPublic,
)
def read_executor_options() -> Any:
    """获取已注册 Executor 任务类型列表（前端下拉使用）"""
    return TaskOptionsPublic(data=list_executor_options())


@router.get(
    "/archive",
    dependencies=[Depends(require_permission("automation_task:view"))],
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
    """获取自动化任务归档列表"""
    return list_automation_task_archives(
        session=session,
        skip=skip,
        limit=limit,
        status=status,
    )


@router.post(
    "/",
    dependencies=[Depends(require_permission("automation_task:create"))],
    response_model=AutomationTaskPublic,
)
def create_automation_task(
    *,
    session: SessionDep,
    task_in: AutomationTaskCreate,
) -> Any:
    """创建自动化任务"""
    try:
        task = create_automation_task_service(session=session, task_in=task_in)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return to_automation_task_public(task)


@router.get(
    "/{id}",
    dependencies=[Depends(require_permission("automation_task:view"))],
    response_model=AutomationTaskPublic,
)
def read_automation_task(
    session: SessionDep,
    id: uuid.UUID,
) -> Any:
    """根据 ID 获取自动化任务"""
    return get_automation_task_public(session=session, task_id=id)


@router.post(
    "/{id}/retry",
    dependencies=[Depends(require_permission("automation_task:manage"))],
    response_model=AutomationTaskPublic,
)
def retry_automation_task(
    session: SessionDep,
    id: uuid.UUID,
) -> Any:
    """手动重试失败任务"""
    try:
        task = retry_automation_task_service(session=session, task_id=id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return to_automation_task_public(task)


@router.post(
    "/{id}/cancel",
    dependencies=[Depends(require_permission("automation_task:manage"))],
    response_model=AutomationTaskPublic,
)
def cancel_automation_task(
    session: SessionDep,
    id: uuid.UUID,
) -> Any:
    """取消待执行任务"""
    try:
        task = cancel_automation_task_service(session=session, task_id=id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return to_automation_task_public(task)
