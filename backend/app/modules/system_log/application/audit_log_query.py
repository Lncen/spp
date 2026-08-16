"""操作审计查询应用服务"""

import uuid
from datetime import datetime

from sqlmodel import Session

from app.modules.system_log.repositories.audit_log import (
    count_audit_logs,
    get_audit_log_or_404,
    list_audit_logs,
)
from app.modules.system_log.schemas.log import AuditLogPublic, AuditLogsPublic


def list_audit_logs_page(
    *,
    session: Session,
    skip: int,
    limit: int,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    actor_id: uuid.UUID | None,
    keyword: str | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> AuditLogsPublic:
    """分页查询操作审计"""
    logs = list_audit_logs(
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
    count = count_audit_logs(
        session=session,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_id=actor_id,
        keyword=keyword,
        start_at=start_at,
        end_at=end_at,
    )
    return AuditLogsPublic(
        data=[AuditLogPublic.model_validate(log) for log in logs],
        count=count,
    )


def get_audit_log(
    *, session: Session, audit_log_id: uuid.UUID
) -> AuditLogPublic:
    """查询单条操作审计"""
    log = get_audit_log_or_404(
        session=session, audit_log_id=audit_log_id
    )
    return AuditLogPublic.model_validate(log)
