"""聊天模块：消息数据访问

消息主键是 UUID v4，因此排序与游标一律使用 `(created_at, id)`，禁止只比较 `id`。
"""

import uuid

from sqlmodel import Session, col, func, or_, select

from app.modules.chat.models import Message


def create_message(
    *,
    session: Session,
    chat_id: uuid.UUID,
    sender_id: uuid.UUID | None,
    message_type: str,
    content: str,
    client_message_id: str | None = None,
    file_name: str | None = None,
    file_path: str | None = None,
) -> Message:
    """创建消息（不提交，由应用层控制事务）"""
    message = Message(
        chat_id=chat_id,
        sender_id=sender_id,
        message_type=message_type,
        content=content,
        client_message_id=client_message_id,
        file_name=file_name,
        file_path=file_path,
    )
    session.add(message)
    return message


def get_message(*, session: Session, message_id: uuid.UUID) -> Message | None:
    """按 ID 获取消息"""
    return session.get(Message, message_id)


def get_message_by_client_id(
    *,
    session: Session,
    sender_id: uuid.UUID,
    client_message_id: str,
) -> Message | None:
    """按客户端幂等键获取消息（用于重复发送时直接返回原消息）"""
    return session.exec(
        select(Message).where(
            col(Message.sender_id) == sender_id,
            col(Message.client_message_id) == client_message_id,
        )
    ).first()


def count_messages(*, session: Session, chat_id: uuid.UUID) -> int:
    """聊天内有效消息总数"""
    return session.exec(
        select(func.count())
        .select_from(Message)
        .where(
            col(Message.chat_id) == chat_id,
            col(Message.is_active).is_(True),
        )
    ).one()


def list_messages(
    *,
    session: Session,
    chat_id: uuid.UUID,
    limit: int,
    before: Message | None = None,
) -> list[Message]:
    """按 `(created_at, id)` 倒序取一页消息；`before` 为翻页游标（取更早的一页）"""
    statement = select(Message).where(
        col(Message.chat_id) == chat_id,
        col(Message.is_active).is_(True),
    )
    if before is not None and before.created_at is not None:
        statement = statement.where(
            or_(
                col(Message.created_at) < before.created_at,
                (
                    (col(Message.created_at) == before.created_at)
                    & (col(Message.id) < before.id)
                ),
            )
        )
    rows = session.exec(
        statement.order_by(
            col(Message.created_at).desc(),
            col(Message.id).desc(),
        ).limit(limit)
    ).all()
    return list(rows)
