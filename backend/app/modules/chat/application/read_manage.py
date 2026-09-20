"""聊天模块：已读与未读数应用服务"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.chat.application.access import get_accessible_chat
from app.modules.chat.domain.ordering import is_after
from app.modules.chat.models import ChatParticipant, Message
from app.modules.chat.repositories.message import get_message
from app.modules.chat.repositories.participant import (
    count_unread_for_chat,
    count_unread_total,
    lock_participant,
    touch_last_read,
)
from app.modules.chat.schemas.chat import ChatReadResult, ChatUnreadCount
from app.modules.user.models import User


def mark_chat_read(
    *,
    session: Session,
    current_user: User,
    chat_id: uuid.UUID,
    message_id: uuid.UUID,
) -> ChatReadResult:
    """把已读游标推进到指定消息（只能向前，客户端重复 / 乱序提交不会回退）"""
    chat, _ = get_accessible_chat(
        session=session, user=current_user, chat_id=chat_id
    )
    message = _get_chat_message(
        session=session, chat_id=chat.id, message_id=message_id
    )
    participant = lock_participant(
        session=session, chat_id=chat.id, user_id=current_user.id
    )
    if participant is None:
        raise HTTPException(status_code=400, detail="无权访问该聊天")
    if _should_advance(
        session=session, participant=participant, message=message
    ):
        touch_last_read(
            session=session,
            participant=participant,
            message_id=message.id,
        )
    session.commit()
    unread = count_unread_for_chat(
        session=session, chat_id=chat.id, user_id=current_user.id
    )
    return ChatReadResult(
        chat_id=chat.id,
        last_read_message_id=participant.last_read_message_id,
        unread_count=unread,
    )


def get_my_unread_count(
    *, session: Session, current_user: User
) -> ChatUnreadCount:
    """当前用户全部聊天的未读消息总数"""
    return ChatUnreadCount(
        unread_count=count_unread_total(
            session=session, user_id=current_user.id
        )
    )


def _get_chat_message(
    *,
    session: Session,
    chat_id: uuid.UUID,
    message_id: uuid.UUID,
) -> Message:
    """读取聊天内的消息，不存在或不属于该聊天时返回 400"""
    message = get_message(session=session, message_id=message_id)
    if message is None or message.chat_id != chat_id:
        raise HTTPException(status_code=400, detail="消息不属于该聊天")
    return message


def _should_advance(
    *,
    session: Session,
    participant: ChatParticipant,
    message: Message,
) -> bool:
    """判断游标是否需要推进（游标为空或目标消息在其之后）"""
    if participant.last_read_message_id is None:
        return True
    current = get_message(
        session=session, message_id=participant.last_read_message_id
    )
    if current is None or current.created_at is None:
        return True
    return is_after(
        created_at=message.created_at,
        message_id=message.id,
        than_created_at=current.created_at,
        than_message_id=current.id,
    )
