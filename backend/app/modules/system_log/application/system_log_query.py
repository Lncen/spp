"""系统日志查询应用服务"""

import uuid
from datetime import datetime

from sqlmodel import Session

from app.modules.system_log.repositories.system_log import (
    count_system_logs,
    get_system_log_or_404,
    list_system_logs,
)
from app.modules.system_log.schemas.log import SystemLogPublic, SystemLogsPublic


def list_system_logs_page(
    *,
    session: Session,
    skip: int,
    limit: int,
    level: str | None,
    module: str | None,
    event_type: str | None,
    status: str | None,
    resource_type: str | None,
    resource_id: str | None,
    keyword: str | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> SystemLogsPublic:
    """分页查询系统日志"""
    logs = list_system_logs(
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
    count = count_system_logs(
        session=session,
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
    return SystemLogsPublic(
        data=[SystemLogPublic.model_validate(log) for log in logs],
        count=count,
    )


def get_system_log(*, session: Session, log_id: uuid.UUID) -> SystemLogPublic:
    """查询单条系统日志"""
    log = get_system_log_or_404(session=session, log_id=log_id)
    return SystemLogPublic.model_validate(log)
