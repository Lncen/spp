"""自动化模块：自动化事件数据访问层"""

import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, delete, or_, update
from sqlmodel import Session, func, select

from app.modules.automation.domain.constants import AutomationEventStatus
from app.modules.automation.models import AutomationEvent

REDISPATCH_GRACE_SECONDS = 60
MAX_DISPATCH_ATTEMPTS = 5
REDISPATCH_RESERVE_SECONDS = 300


def create_event(
    *,
    session: Session,
    event_type: str,
    payload: dict[str, Any],
) -> AutomationEvent:
    """创建事件记录（不提交，由调用方控制事务）。"""
    event = AutomationEvent(event_type=event_type, payload=payload)
    session.add(event)
    return event


def get_event_or_404(*, session: Session, event_id: uuid.UUID) -> AutomationEvent:
    """按 ID 获取事件，不存在时抛出 404。"""
    event = session.get(AutomationEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="自动化事件不存在")
    return event


def count_events(*, session: Session, event_type: str | None) -> int:
    """统计事件总数，可按事件类型过滤。"""
    stmt = select(func.count()).select_from(AutomationEvent)
    if event_type is not None:
        stmt = stmt.where(AutomationEvent.event_type == event_type)
    return session.exec(stmt).one()


def list_events(
    *,
    session: Session,
    skip: int,
    limit: int,
    event_type: str | None,
) -> list[AutomationEvent]:
    """分页查询事件，可按事件类型过滤，最新在前。"""
    stmt = (
        select(AutomationEvent)
        .order_by(AutomationEvent.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if event_type is not None:
        stmt = stmt.where(AutomationEvent.event_type == event_type)
    return session.exec(stmt).all()


def map_event_types(
    *,
    session: Session,
    event_ids: set[uuid.UUID],
) -> dict[uuid.UUID, str]:
    """批量查询事件 ID → 事件类型，避免逐条查询造成 N+1。"""
    if not event_ids:
        return {}
    return {
        event.id: event.event_type
        for event in session.exec(
            select(AutomationEvent).where(AutomationEvent.id.in_(event_ids))
        ).all()
    }


def purge_events(
    *,
    session: Session,
    before: datetime,
    limit: int,
) -> int:
    """物理删除创建时间早于 before 的自动化事件，返回删除数量。"""
    ids = session.exec(
        select(AutomationEvent.id)
        .where(AutomationEvent.created_at < before)
        .limit(limit)
    ).all()
    if not ids:
        return 0
    session.exec(
        delete(AutomationEvent).where(AutomationEvent.id.in_(ids))
    )
    session.commit()
    return len(ids)


def claim_events_for_redispatch(
    *,
    session: Session,
    now: datetime,
    limit: int,
) -> list[AutomationEvent]:
    """原子认领需要补发的事件，多 worker 并发时只认领本事务真正更新的行。"""
    grace_cutoff = now - timedelta(seconds=REDISPATCH_GRACE_SECONDS)
    retryable_statuses = [
        AutomationEventStatus.PENDING,
        AutomationEventStatus.DISPATCHING,
        AutomationEventStatus.FAILED,
    ]
    ids = session.exec(
        select(AutomationEvent.id)
        .where(
            AutomationEvent.status.in_(retryable_statuses),
            AutomationEvent.dispatch_attempts < MAX_DISPATCH_ATTEMPTS,
            or_(
                and_(
                    AutomationEvent.next_dispatch_at.is_(None),
                    AutomationEvent.created_at <= grace_cutoff,
                ),
                and_(
                    AutomationEvent.next_dispatch_at.is_not(None),
                    AutomationEvent.next_dispatch_at <= now,
                ),
            ),
        )
        .order_by(AutomationEvent.created_at.asc())
        .limit(limit)
    ).all()
    if not ids:
        return []

    claimed_ids = session.execute(
        update(AutomationEvent)
        .where(
            AutomationEvent.id.in_(ids),
            AutomationEvent.status.in_(retryable_statuses),
            AutomationEvent.dispatch_attempts < MAX_DISPATCH_ATTEMPTS,
            or_(
                and_(
                    AutomationEvent.next_dispatch_at.is_(None),
                    AutomationEvent.created_at <= grace_cutoff,
                ),
                and_(
                    AutomationEvent.next_dispatch_at.is_not(None),
                    AutomationEvent.next_dispatch_at <= now,
                ),
            ),
        )
        .values(
            status=AutomationEventStatus.DISPATCHING,
            processing_at=now,
            next_dispatch_at=now + timedelta(seconds=REDISPATCH_RESERVE_SECONDS),
        )
        .returning(AutomationEvent.id)
    ).scalars().all()
    session.commit()
    if not claimed_ids:
        return []

    return session.exec(
        select(AutomationEvent)
        .where(AutomationEvent.id.in_(claimed_ids))
        .order_by(AutomationEvent.created_at.asc())
    ).all()
