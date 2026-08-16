"""系统日志数据访问"""

import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, func, or_, select

from app.modules.system_log.domain.event_mapping import SystemLogRecord
from app.modules.system_log.models import SystemLog


def create_system_log(*, session: Session, record: SystemLogRecord) -> SystemLog:
    """创建系统日志并加入会话（不提交，由调用方控制事务）"""
    log = SystemLog(
        level=record.level.value,
        event_type=record.event_type,
        module=record.module,
        actor_type=record.actor_type,
        actor_id=record.actor_id,
        resource_type=record.resource_type,
        resource_id=record.resource_id,
        event_id=record.event_id,
        request_id=record.request_id,
        trace_id=record.trace_id,
        business_id=record.business_id,
        task_id=record.task_id,
        status=record.status.value,
        error_code=record.error_code,
        error_message=record.error_message,
        context=record.context,
    )
    session.add(log)
    return log


def get_system_log_or_404(*, session: Session, log_id: uuid.UUID) -> SystemLog:
    """按 ID 获取系统日志，不存在时抛出 404"""
    log = session.get(SystemLog, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="系统日志不存在")
    return log


def _keyword_filter(keyword: str | None) -> ColumnElement[bool] | None:
    """构造系统日志模糊匹配条件，无关键字时返回 None"""
    if not keyword:
        return None
    pattern = f"%{keyword.strip()}%"
    return or_(
        col(SystemLog.event_type).ilike(pattern),
        col(SystemLog.resource_id).ilike(pattern),
        col(SystemLog.business_id).ilike(pattern),
        col(SystemLog.error_code).ilike(pattern),
        col(SystemLog.error_message).ilike(pattern),
    )


def _build_filters(
    *,
    level: str | None,
    module: str | None,
    event_type: str | None,
    status: str | None,
    resource_type: str | None,
    resource_id: str | None,
    keyword: str | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> list[ColumnElement[bool]]:
    """构造系统日志查询条件列表"""
    filters: list[ColumnElement[bool]] = []
    if level:
        filters.append(col(SystemLog.level) == level)
    if module:
        filters.append(col(SystemLog.module) == module)
    if event_type:
        filters.append(col(SystemLog.event_type) == event_type)
    if status:
        filters.append(col(SystemLog.status) == status)
    if resource_type:
        filters.append(col(SystemLog.resource_type) == resource_type)
    if resource_id:
        filters.append(col(SystemLog.resource_id) == resource_id)
    keyword_filter = _keyword_filter(keyword)
    if keyword_filter is not None:
        filters.append(keyword_filter)
    if start_at:
        filters.append(col(SystemLog.created_at) >= start_at)
    if end_at:
        filters.append(col(SystemLog.created_at) <= end_at)
    return filters


def list_system_logs(
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
) -> list[SystemLog]:
    """分页查询系统日志，最新在前"""
    stmt = (
        select(SystemLog)
        .where(
            *_build_filters(
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
        )
        .order_by(col(SystemLog.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(stmt).all())


def count_system_logs(
    *,
    session: Session,
    level: str | None,
    module: str | None,
    event_type: str | None,
    status: str | None,
    resource_type: str | None,
    resource_id: str | None,
    keyword: str | None,
    start_at: datetime | None,
    end_at: datetime | None,
) -> int:
    """统计系统日志总数（与列表同条件）"""
    stmt = select(func.count()).select_from(SystemLog).where(
        *_build_filters(
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
    )
    return session.exec(stmt).one()
