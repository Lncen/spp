"""通知中心：渠道投递记录数据访问"""

import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlmodel import Session, col, update

from app.core.time import get_datetime_cn
from app.modules.notification.domain.constants import (
    DEFAULT_MAX_ATTEMPTS,
    DeliveryStatus,
)
from app.modules.notification.models import NotificationDelivery


def create_delivery(
    *,
    session: Session,
    notification_id: uuid.UUID,
    channel: str,
    status: str = DeliveryStatus.PENDING,
) -> NotificationDelivery:
    """创建投递记录并加入会话（不提交，由调用方控制事务）

    `status=SENT` 用于站内通知：通知落库即视为送达，不经过异步投递。
    """
    delivery = NotificationDelivery(
        notification_id=notification_id,
        channel=channel,
        status=status,
        attempt_count=0,
        max_attempts=DEFAULT_MAX_ATTEMPTS,
        sent_at=get_datetime_cn() if status == DeliveryStatus.SENT else None,
    )
    session.add(delivery)
    return delivery


def get_delivery_or_404(
    *,
    session: Session,
    delivery_id: uuid.UUID,
) -> NotificationDelivery:
    """按 ID 获取投递记录，不存在时抛 404"""
    delivery = session.get(NotificationDelivery, delivery_id)
    if delivery is None:
        raise HTTPException(status_code=404, detail="投递记录不存在")
    return delivery


def reset_delivery_for_retry(
    *,
    session: Session,
    delivery: NotificationDelivery,
) -> NotificationDelivery:
    """将投递记录重置为待发送并清空错误信息（重试为新一轮尝试）"""
    delivery.status = DeliveryStatus.PENDING
    delivery.attempt_count = 0
    delivery.error_message = None
    session.add(delivery)
    return delivery


def claim_delivery_for_sending(
    *,
    session: Session,
    delivery_id: uuid.UUID,
) -> NotificationDelivery | None:
    """幂等认领投递：仅 pending/failed 状态可进入 sending 并累加尝试次数。

    使用条件更新保证并发下只有一个执行者能认领成功（其余返回 None 直接跳过），
    防止 Celery 消息重投或兜底扫描重复入队造成重复发送。
    """
    result = session.exec(
        update(NotificationDelivery)
        .where(
            NotificationDelivery.id == delivery_id,
            NotificationDelivery.status.in_(
                [DeliveryStatus.PENDING, DeliveryStatus.FAILED]
            ),
        )
        .values(
            status=DeliveryStatus.SENDING,
            attempt_count=NotificationDelivery.attempt_count + 1,
            updated_at=get_datetime_cn(),
        )
    )
    if result.rowcount == 0:
        return None
    # 认领状态立即提交：投递尝试已发生，失败回滚不应回退 SENDING/尝试次数
    session.commit()
    return session.get(NotificationDelivery, delivery_id)


def recover_stale_deliveries(
    *,
    session: Session,
    before: datetime,
    now: datetime,
) -> list[uuid.UUID]:
    """将超时未推进的投递原子重置为 pending，返回可重新入队的投递 ID。

    pending 说明原任务丢失（从未入队/消息丢失），sending 说明 worker 中断；
    重置为 pending 后由兜底任务重新入队，deliver 任务的幂等认领保证不重复发送。
    """
    result = session.execute(
        update(NotificationDelivery)
        .where(
            NotificationDelivery.status.in_(
                [DeliveryStatus.PENDING, DeliveryStatus.SENDING]
            ),
            col(NotificationDelivery.updated_at).is_not(None),
            col(NotificationDelivery.updated_at) < before,
        )
        .values(
            status=DeliveryStatus.PENDING,
            updated_at=now,
        )
        .returning(NotificationDelivery.id)
    )
    stale_ids = list(result.scalars().all())
    session.commit()
    return stale_ids
