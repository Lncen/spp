"""系统日志与操作审计只读查询 API"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, require_permission
from app.modules.system_log.application.audit_log_query import (
    get_audit_log,
    list_audit_logs_page,
)
from app.modules.system_log.application.system_log_query import (
    get_system_log,
    list_system_logs_page,
)
from app.modules.system_log.schemas.log import (
    AuditLogPublic,
    AuditLogsPublic,
    SystemLogPublic,
    SystemLogsPublic,
)

router = APIRouter(tags=["system_logs"])


@router.get(
    "/system-logs/",
    dependencies=[Depends(require_permission("system_log:view"))],
    response_model=SystemLogsPublic,
)
def read_system_logs(
    session: SessionDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    level: Annotated[str | None, Query(max_length=16)] = None,
    module: Annotated[str | None, Query(max_length=64)] = None,
    event_type: Annotated[str | None, Query(max_length=128)] = None,
    status: Annotated[str | None, Query(max_length=32)] = None,
    resource_type: Annotated[str | None, Query(max_length=64)] = None,
    resource_id: Annotated[str | None, Query(max_length=128)] = None,
    keyword: Annotated[str | None, Query(max_length=128)] = None,
    start_at: Annotated[datetime | None, Query()] = None,
    end_at: Annotated[datetime | None, Query()] = None,
) -> SystemLogsPublic:
    """分页查询系统日志"""
    return list_system_logs_page(
        session=session,
        skip=skip,
        limit=limit,
        level=level,
        module=module,
        event_type=event_type,
        status=status,
        resource_type=resource_type,
        resource_id=resource_id,
        keyword=keyword,
        start_at=start_at,
        end_at=end_at,
    )


@router.get(
    "/system-logs/{log_id}",
    dependencies=[Depends(require_permission("system_log:view"))],
    response_model=SystemLogPublic,
)
def read_system_log(*, session: SessionDep, log_id: uuid.UUID) -> SystemLogPublic:
    """查询单条系统日志详情"""
    return get_system_log(session=session, log_id=log_id)


@router.get(
    "/audit-logs/",
    dependencies=[Depends(require_permission("audit_log:view"))],
    response_model=AuditLogsPublic,
)
def read_audit_logs(
    session: SessionDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    action: Annotated[str | None, Query(max_length=128)] = None,
    resource_type: Annotated[str | None, Query(max_length=64)] = None,
    resource_id: Annotated[str | None, Query(max_length=128)] = None,
    actor_id: Annotated[uuid.UUID | None, Query()] = None,
    keyword: Annotated[str | None, Query(max_length=128)] = None,
    start_at: Annotated[datetime | None, Query()] = None,
    end_at: Annotated[datetime | None, Query()] = None,
) -> AuditLogsPublic:
    """分页查询操作审计"""
    return list_audit_logs_page(
        session=session,
        skip=skip,
        limit=limit,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_id=actor_id,
        keyword=keyword,
        start_at=start_at,
        end_at=end_at,
    )


@router.get(
    "/audit-logs/{audit_log_id}",
    dependencies=[Depends(require_permission("audit_log:view"))],
    response_model=AuditLogPublic,
)
def read_audit_log(
    *, session: SessionDep, audit_log_id: uuid.UUID
) -> AuditLogPublic:
    """查询单条操作审计详情"""
    return get_audit_log(session=session, audit_log_id=audit_log_id)
