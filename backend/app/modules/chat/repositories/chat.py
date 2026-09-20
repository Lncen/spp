"""聊天模块：聊天数据访问"""

import uuid
from datetime import datetime

from sqlmodel import Session, col, func, select

from app.modules.chat.domain.constants import ChatStatus
from app.modules.chat.models import Chat, ChatParticipant


def create_chat(
    *,
    session: Session,
    chat_type: str,
    direct_key: str | None = None,
    name: str | None = None,
) -> Chat:
    """创建聊天记录（不提交，由应用层控制事务）"""
    chat = Chat(
        type=chat_type,
        direct_key=direct_key,
        name=name,
    )
    session.add(chat)
    return chat


def get_chat(*, session: Session, chat_id: uuid.UUID) -> Chat | None:
    """按 ID 获取聊天"""
    return session.get(Chat, chat_id)


def get_direct_chat(*, session: Session, direct_key: str) -> Chat | None:
    """按私聊唯一键获取聊天（双向私聊命中同一条）"""
    return session.exec(
        select(Chat).where(col(Chat.direct_key) == direct_key)
    ).first()


def lock_chat(*, session: Session, chat_id: uuid.UUID) -> Chat | None:
    """锁定聊天行（发送消息时用于串行化 last_message 更新）"""
    return session.exec(
        select(Chat).where(col(Chat.id) == chat_id).with_for_update()
    ).first()


def list_chats_for_user(
    *,
    session: Session,
    user_id: uuid.UUID,
    skip: int,
    limit: int,
) -> tuple[int, list[Chat]]:
    """当前用户参与的聊天列表（最后消息时间倒序，无消息的排最后）"""
    condition = col(ChatParticipant.chat_id) == col(Chat.id)
    count = session.exec(
        select(func.count())
        .select_from(Chat)
        .join(ChatParticipant, condition)
        .where(col(ChatParticipant.user_id) == user_id)
    ).one()
    chats = session.exec(
        select(Chat)
        .join(ChatParticipant, condition)
        .where(col(ChatParticipant.user_id) == user_id)
        .order_by(
            col(Chat.last_message_at).desc().nullslast(),
            col(Chat.created_at).desc(),
            col(Chat.id).desc(),
        )
        .offset(skip)
        .limit(limit)
    ).all()
    return count, list(chats)


def advance_last_message(
    *,
    session: Session,
    chat: Chat,
    message_id: uuid.UUID,
    created_at: datetime,
    preview: str,
) -> None:
    """更新聊天的最后消息冗余（调用方需已按 `(created_at, id)` 判断方向并持有行锁）"""
    chat.last_message_id = message_id
    chat.last_message_at = created_at
    chat.last_message_preview = preview[:200]
    chat.status = ChatStatus.ACTIVE
    session.add(chat)
