"""客服模块：消息数据访问"""

import uuid
from datetime import datetime

from sqlalchemy import or_
from sqlmodel import Session, col, select, update

from app.modules.customer_service.models import ConversationMessage


def create_message(
    *,
    session: Session,
    conversation_id: uuid.UUID,
    sender_id: uuid.UUID,
    sender_role: str,
    content: str,
) -> ConversationMessage:
    """创建消息"""
    message = ConversationMessage(
        conversation_id=conversation_id,
        sender_id=sender_id,
        sender_role=sender_role,
        content=content,
    )
    session.add(message)
    session.flush()
    return message


def list_messages(
    *,
    session: Session,
    conversation_id: uuid.UUID,
    limit: int,
    before_id: uuid.UUID | None = None,
) -> list[ConversationMessage]:
    """查询会话消息（最新在前）；传入 before_id 时返回该消息之前更早的一页"""
    query = (
        select(ConversationMessage)
        .where(col(ConversationMessage.conversation_id) == conversation_id)
        .order_by(
            ConversationMessage.created_at.desc(),
            ConversationMessage.id.desc(),
        )
        .limit(limit)
    )
    if before_id is not None:
        before = session.get(ConversationMessage, before_id)
        if before is None or before.created_at is None:
            return []
        query = query.where(
            or_(
                ConversationMessage.created_at < before.created_at,
                (ConversationMessage.created_at == before.created_at)
                & (ConversationMessage.id < before_id),
            )
        )
    return session.exec(query).all()


def mark_messages_read(
    *,
    session: Session,
    conversation_id: uuid.UUID,
    reader_role: str,
    now: datetime,
) -> int:
    """将对方发来且未读的消息标记为已读，返回更新条数"""
    result = session.exec(
        update(ConversationMessage)
        .where(
            col(ConversationMessage.conversation_id) == conversation_id,
            col(ConversationMessage.sender_role) != reader_role,
            col(ConversationMessage.read_at).is_(None),
        )
        .values(read_at=now)
    )
    return result.rowcount or 0
