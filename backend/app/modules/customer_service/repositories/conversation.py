"""客服模块：会话数据访问"""

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.modules.customer_service.domain.constants import ConversationStatus
from app.modules.customer_service.models import Conversation, ConversationMessage


def create_conversation(
    *,
    session: Session,
    user_id: uuid.UUID,
) -> Conversation:
    """创建会话"""
    conversation = Conversation(user_id=user_id)
    session.add(conversation)
    session.flush()
    return conversation


def get_conversation(
    *,
    session: Session,
    conversation_id: uuid.UUID,
) -> Conversation | None:
    """按 ID 获取会话"""
    return session.get(Conversation, conversation_id)


def get_open_conversation_by_user(
    *,
    session: Session,
    user_id: uuid.UUID,
) -> Conversation | None:
    """获取用户的进行中会话"""
    return session.exec(
        select(Conversation)
        .where(
            col(Conversation.user_id) == user_id,
            col(Conversation.status) == ConversationStatus.OPEN,
        )
        .order_by(Conversation.created_at.desc())
    ).first()


def list_conversations_by_user(
    *,
    session: Session,
    user_id: uuid.UUID,
    skip: int,
    limit: int,
) -> tuple[int, list[Conversation]]:
    """分页查询用户自己的会话"""
    stmt = select(Conversation).where(col(Conversation.user_id) == user_id)
    count = len(session.exec(stmt).all())
    conversations = session.exec(
        stmt.order_by(Conversation.last_message_at.desc(), Conversation.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return count, list(conversations)


def list_all_conversations(
    *,
    session: Session,
    skip: int,
    limit: int,
) -> tuple[int, list[Conversation]]:
    """分页查询全部会话（管理端）"""
    stmt = select(Conversation)
    count = len(session.exec(stmt).all())
    conversations = session.exec(
        stmt.order_by(Conversation.last_message_at.desc(), Conversation.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return count, list(conversations)


def count_unread_messages(
    *,
    session: Session,
    conversation_ids: list[uuid.UUID],
    reader_id: uuid.UUID,
) -> dict[uuid.UUID, int]:
    """批量统计各会话中他人发来且当前查看者未读的消息数（不区分发送方角色）"""
    if not conversation_ids:
        return {}
    rows = session.exec(
        select(
            ConversationMessage.conversation_id,
            func.count(),
        )
        .where(
            col(ConversationMessage.conversation_id).in_(conversation_ids),
            col(ConversationMessage.sender_id) != reader_id,
            col(ConversationMessage.read_at).is_(None),
        )
        .group_by(ConversationMessage.conversation_id)
    ).all()
    return dict(rows)


def count_unread_total(
    *,
    session: Session,
    user_id: uuid.UUID,
    is_superuser: bool,
) -> int:
    """统计当前查看者可见会话中他人发来且未读的消息总数（管理端统计全部会话，不区分发送方角色）"""
    stmt = (
        select(func.count())
        .select_from(ConversationMessage)
        .join(Conversation, Conversation.id == ConversationMessage.conversation_id)
        .where(
            col(ConversationMessage.sender_id) != user_id,
            col(ConversationMessage.read_at).is_(None),
        )
    )
    if not is_superuser:
        stmt = stmt.where(col(Conversation.user_id) == user_id)
    return session.exec(stmt).one() or 0


def touch_conversation(
    *,
    conversation: Conversation,
    now: datetime,
    preview: str,
) -> None:
    """更新会话最后消息时间与预览"""
    conversation.last_message_at = now
    conversation.last_message_preview = preview[:200]


def set_conversation_status(
    *,
    conversation: Conversation,
    status: str,
) -> None:
    """更新会话状态"""
    conversation.status = status
