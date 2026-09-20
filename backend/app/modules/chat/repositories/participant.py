"""聊天模块：聊天成员（成员关系 + 已读游标）数据访问

未读数由「消息顺序 + 已读游标」推算，不额外建读状态表：
`(created_at, id) > 已读消息的 (created_at, id)` 且发送者不是自己。
"""

import uuid

from sqlalchemy import and_, func, or_, tuple_
from sqlalchemy.orm import aliased
from sqlmodel import Session, col, select

from app.modules.chat.domain.constants import ParticipantRole
from app.modules.chat.models import ChatParticipant, Message


def add_participant(
    *,
    session: Session,
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str = ParticipantRole.MEMBER,
    last_read_message_id: uuid.UUID | None = None,
) -> ChatParticipant:
    """加入聊天（不提交，由应用层控制事务）"""
    participant = ChatParticipant(
        chat_id=chat_id,
        user_id=user_id,
        role=role,
        last_read_message_id=last_read_message_id,
    )
    session.add(participant)
    return participant


def get_participant(
    *,
    session: Session,
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ChatParticipant | None:
    """获取成员记录"""
    return session.exec(
        select(ChatParticipant).where(
            col(ChatParticipant.chat_id) == chat_id,
            col(ChatParticipant.user_id) == user_id,
        )
    ).first()


def lock_participant(
    *,
    session: Session,
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ChatParticipant | None:
    """锁定成员行（已读游标只允许向前推进，需要串行化比较）"""
    return session.exec(
        select(ChatParticipant)
        .where(
            col(ChatParticipant.chat_id) == chat_id,
            col(ChatParticipant.user_id) == user_id,
        )
        .with_for_update()
    ).first()


def list_participants(
    *, session: Session, chat_id: uuid.UUID
) -> list[ChatParticipant]:
    """聊天成员列表（按加入时间排序）"""
    return list(
        session.exec(
            select(ChatParticipant)
            .where(col(ChatParticipant.chat_id) == chat_id)
            .order_by(col(ChatParticipant.joined_at).asc())
        ).all()
    )


def list_participant_user_ids(
    *, session: Session, chat_id: uuid.UUID
) -> list[uuid.UUID]:
    """聊天成员用户 ID 列表（实时发布与提醒用）"""
    return list(
        session.exec(
            select(ChatParticipant.user_id).where(
                col(ChatParticipant.chat_id) == chat_id
            )
        ).all()
    )


def delete_participant(
    *, session: Session, participant: ChatParticipant
) -> None:
    """移除成员（不提交，由应用层控制事务）"""
    session.delete(participant)


def touch_last_read(
    *,
    session: Session,
    participant: ChatParticipant,
    message_id: uuid.UUID,
) -> None:
    """推进已读游标（调用方需已确认方向并持有行锁）"""
    participant.last_read_message_id = message_id
    session.add(participant)


def _unread_statement(*, user_id: uuid.UUID):
    """未读数聚合语句：按聊天分组统计「游标之后、非本人发送」的消息"""
    cursor = aliased(Message)
    return (
        select(Message.chat_id, func.count())
        .join(
            ChatParticipant,
            and_(
                col(ChatParticipant.chat_id) == col(Message.chat_id),
                col(ChatParticipant.user_id) == user_id,
            ),
        )
        .outerjoin(cursor, col(cursor.id) == col(ChatParticipant.last_read_message_id))
        .where(
            col(Message.is_active).is_(True),
            col(Message.sender_id) != user_id,
            or_(
                col(cursor.id).is_(None),
                tuple_(col(Message.created_at), col(Message.id))
                > tuple_(col(cursor.created_at), col(cursor.id)),
            ),
        )
        .group_by(col(Message.chat_id))
    )


def count_unread_by_chat(
    *,
    session: Session,
    user_id: uuid.UUID,
    chat_ids: list[uuid.UUID] | None = None,
) -> dict[uuid.UUID, int]:
    """按聊天统计未读数（一次查询覆盖当前用户的全部聊天）"""
    statement = _unread_statement(user_id=user_id)
    if chat_ids is not None:
        if not chat_ids:
            return {}
        statement = statement.where(col(Message.chat_id).in_(chat_ids))
    return {
        chat_id: int(count)
        for chat_id, count in session.exec(statement).all()
    }


def count_unread_total(*, session: Session, user_id: uuid.UUID) -> int:
    """当前用户全部聊天的未读消息总数"""
    return sum(count_unread_by_chat(session=session, user_id=user_id).values())


def count_unread_for_chat(
    *,
    session: Session,
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    """单个聊天的未读数"""
    counts = count_unread_by_chat(
        session=session, user_id=user_id, chat_ids=[chat_id]
    )
    return counts.get(chat_id, 0)
