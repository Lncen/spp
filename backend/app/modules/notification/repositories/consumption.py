"""通知中心：事件消费状态数据访问"""

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, update
from sqlmodel import Session, col, select

from app.core.time import get_datetime_cn
from app.modules.notification.domain.constants import (
    CONSUMPTION_MAX_ATTEMPTS,
    ConsumptionStatus,
)
from app.modules.notification.models import NotificationEventConsumption


def get_consumption(
    *, session: Session, event_id: uuid.UUID
) -> NotificationEventConsumption | None:
    """按事件 ID 查询消费状态"""
    return session.exec(
        select(NotificationEventConsumption).where(
            col(NotificationEventConsumption.event_id) == event_id
        )
    ).first()


def claim_due_consumptions(
    *,
    session: Session,
    now: datetime,
    stale_cutoff: datetime,
    limit: int,
) -> list[uuid.UUID]:
    """原子认领待重试的消费记录，返回事件 ID 列表

    可重试的场景：

    - `pending` / `failed` 且未超过尝试上限、退避时间已到；
    - `processing` 但更新时间早于 `stale_cutoff`（消费过程中 worker 中断）。
    """
    condition = or_(
        and_(
            col(NotificationEventConsumption.status).in_(
                [ConsumptionStatus.PENDING, ConsumptionStatus.FAILED]
            ),
            col(NotificationEventConsumption.attempt_count)
            < CONSUMPTION_MAX_ATTEMPTS,
            or_(
                col(NotificationEventConsumption.next_retry_at).is_(None),
                col(NotificationEventConsumption.next_retry_at) <= now,
            ),
        ),
        and_(
            col(NotificationEventConsumption.status)
            == ConsumptionStatus.PROCESSING,
            col(NotificationEventConsumption.updated_at) < stale_cutoff,
        ),
    )
    ids = session.exec(
        select(NotificationEventConsumption.id)
        .where(condition)
        .order_by(col(NotificationEventConsumption.created_at).asc())
        .limit(limit)
    ).all()
    if not ids:
        return []
    claimed = (
        session.execute(
            update(NotificationEventConsumption)
            .where(
                col(NotificationEventConsumption.id).in_(ids),
                condition,
            )
            .values(
                status=ConsumptionStatus.PROCESSING,
                updated_at=get_datetime_cn(),
            )
            .returning(NotificationEventConsumption.event_id)
        )
        .scalars()
        .all()
    )
    session.commit()
    return list(claimed)
