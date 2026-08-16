"""操作审计数据访问"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, func, or_, select

from app.modules.system_log.models import AuditLog


def create_audit_log(
    *,
    session: Session,
    actor_id: uuid.UUID | None,
    actor_identifier: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    before: dict[str, Any],
    after: dict[str, Any],
    changes: dict[str, Any],
    ip: str | None,
    user_agent: str | None,
    request_id: str | None,
    event_id: uuid.UUID | None = None,
) -> AuditLog:
    """创建审计日志并加入会话（不提交，由调用方控制事务）"""
    audit_log = AuditLog(
        actor_id=actor_id,
        actor_identifier=actor_identifier,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before=before,
        after=after,
        changes=changes,
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
        event_id=event_id,
    )
    session.add(audit_log)
    return audit_log


def get_audit_log_or_404(
    *, session: Session, audit_log_id: uuid.UUID
) -> AuditLog:
    """按 ID 获取审计日志，不存在时抛出 404"""
    audit_log = session.get(AuditLog, audit_log_id)
    if audit_log is None:
        raise HTTPException(status_code=404, detail="操作审计不存在")
    return audit_log


def _keyword_filter(keyword: str | None) -> ColumnElement[bool] | None:
    """构造审计日志模糊匹配条件，无关键字时返回 None"""
    if not keyword:
        return None
    pattern = f"%{keyword.strip()}%"
    return or_(
        col(AuditLog.action).ilike(pattern),
        col(AuditLog.resource_id).ilike(pattern),
        col(AuditLog.actor_identifier).ilike(pattern),
        col(AuditLog.ip).ilike(pattern),
    )


def _build_filters(
    *,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    actor_id: uuid.UUID | None,
    keyword: str | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[ColumnElement[bool]]:
    """构造审计日志查询条件列表"""
    filters: list[ColumnElement[bool]] = []
    if action:
        filters.append(col(AuditLog.action) == action)
    if resource_type:
        filters.append(col(AuditLog.resource_type) == resource_type)
    if resource_id:
        filters.append(col(AuditLog.resource_id) == resource_id)
    if actor_id:
        filters.append(col(AuditLog.actor_id) == actor_id)
    keyword_filter = _keyword_filter(keyword)
    if keyword_filter is not None:
        filters.append(keyword_filter)
    if start_at:
        filters.append(col(AuditLog.created_at) >= start_at)
    if end_at:
        filters.append(col(AuditLog.created_at) <= end_at)
    return filters


def list_audit_logs(
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
) -> list[AuditLog]:
    """分页查询审计日志，最新在前"""
    stmt = (
        select(AuditLog)
        .where(
            *_build_filters(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                actor_id=actor_id,
                keyword=keyword,
                start_at=start_at,
                end_at=end_at,
            )
        )
        .order_by(col(AuditLog.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(stmt).all())


def count_audit_logs(
    *,
    session: Session,
    action: str | None,
    resource_type: str | None,
    resource_id: str | None,
    actor_id: uuid.UUID | None,
    keyword: str | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> int:
    """统计审计日志总数（与列表同条件）"""
    stmt = select(func.count()).select_from(AuditLog).where(
        *_build_filters(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=actor_id,
            keyword=keyword,
            start_at=start_at,
            end_at=end_at,
        )
    )
    return session.exec(stmt).one()
