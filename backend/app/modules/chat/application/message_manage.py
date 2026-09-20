"""聊天模块：消息应用服务（查询 / 发送）"""

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.modules.chat.application.access import get_accessible_chat
from app.modules.chat.domain.constants import (
    ChatType,
    ParticipantRole,
    parse_direct_key,
)
from app.modules.chat.domain.ordering import build_preview, is_after
from app.modules.chat.models import Chat, Message
from app.modules.chat.repositories.chat import advance_last_message, lock_chat
from app.modules.chat.repositories.message import (
    count_messages,
    create_message,
    get_message,
    get_message_by_client_id,
    list_messages,
)
from app.modules.chat.repositories.participant import (
    add_participant,
    get_participant,
    list_participant_user_ids,
)
from app.modules.chat.schemas.message import (
    MessageCreate,
    MessagePublic,
    MessagesPublic,
)
from app.modules.user.application.user_display import (
    load_users,
    user_display_name,
)
from app.modules.user.models import User


def list_chat_messages(
    *,
    session: Session,
    current_user: User,
    chat_id: uuid.UUID,
    limit: int,
    before_id: uuid.UUID | None = None,
) -> MessagesPublic:
    """按游标分页查询聊天消息（最新在前，`before_id` 取更早一页）"""
    chat, _ = get_accessible_chat(
        session=session, user=current_user, chat_id=chat_id
    )
    before = None
    if before_id is not None:
        before = get_message(session=session, message_id=before_id)
        if before is None or before.chat_id != chat.id:
            raise HTTPException(status_code=400, detail="游标消息不属于该聊天")
    messages = list_messages(
        session=session,
        chat_id=chat.id,
        limit=limit,
        before=before,
    )
    total = count_messages(session=session, chat_id=chat.id)
    return MessagesPublic(
        data=to_message_items(session=session, messages=messages),
        count=total,
    )


def send_chat_message(
    *,
    session: Session,
    current_user: User,
    chat_id: uuid.UUID,
    payload: MessageCreate,
) -> tuple[Message, list[uuid.UUID]]:
    """发送消息，返回「消息 + 接收人用户 ID 列表」

    顺序固定为「先落 PostgreSQL，提交成功后由调用方发布实时事件」：

    1. 校验访问权（成员 / 坐席）；
    2. `client_message_id` 幂等：命中已有消息直接返回，不重复落库；
    3. 锁定聊天行后写消息并推进 `last_message_*`（只允许向前，避免并发回退）；
    4. 提交事务。
    """
    chat, _ = get_accessible_chat(
        session=session, user=current_user, chat_id=chat_id
    )
    if payload.client_message_id:
        existing = get_message_by_client_id(
            session=session,
            sender_id=current_user.id,
            client_message_id=payload.client_message_id,
        )
        if existing is not None:
            return existing, []

    locked_chat = lock_chat(session=session, chat_id=chat.id)
    if locked_chat is None:
        raise HTTPException(status_code=404, detail="聊天不存在")
    try:
        message = create_message(
            session=session,
            chat_id=chat.id,
            sender_id=current_user.id,
            message_type=payload.message_type,
            content=payload.content,
            client_message_id=payload.client_message_id,
            file_name=payload.file_name,
            file_path=payload.file_path,
        )
        session.flush()
        # 接收人要在推进 last_message 之前解析：私聊补回对方成员行时，
        # 位点取「本条之前的最后一条」，这样对方只会看到这一条未读
        recipients = _resolve_recipients(
            session=session, chat=locked_chat, sender_id=current_user.id
        )
        advance_last_message_if_newer(
            session=session, chat=locked_chat, message=message
        )
        session.commit()
    except IntegrityError:
        # 并发重试命中 (sender_id, client_message_id) 唯一约束：返回首次落库的消息
        session.rollback()
        if not payload.client_message_id:
            raise
        existing = get_message_by_client_id(
            session=session,
            sender_id=current_user.id,
            client_message_id=payload.client_message_id,
        )
        if existing is None:
            raise
        return existing, []
    session.refresh(message)
    return message, recipients


def _resolve_recipients(
    *,
    session: Session,
    chat: Chat,
    sender_id: uuid.UUID,
) -> list[uuid.UUID]:
    """解析本次消息的接收人

    - 私聊：由 `direct_key` 决定，与当前成员行无关；对方不在列表里（删除了会话）时补回成员行，
      位点设为「本条之前的最后一条」，于是对方只会收到这一条未读并重新出现在列表里；
    - 群聊：当前其余成员。
    """
    if chat.type == ChatType.DIRECT and chat.direct_key:
        direct_users = parse_direct_key(chat.direct_key)
        recipients = [user_id for user_id in direct_users if user_id != sender_id]
    else:
        recipients = [
            user_id
            for user_id in list_participant_user_ids(
                session=session, chat_id=chat.id
            )
            if user_id != sender_id
        ]
    for recipient_id in recipients:
        if (
            get_participant(
                session=session, chat_id=chat.id, user_id=recipient_id
            )
            is None
        ):
            add_participant(
                session=session,
                chat_id=chat.id,
                user_id=recipient_id,
                role=ParticipantRole.MEMBER,
                last_read_message_id=chat.last_message_id,
            )
    return recipients


def advance_last_message_if_newer(
    *,
    session: Session,
    chat: Chat,
    message: Message,
) -> bool:
    """按 `(created_at, id)` 判断方向，只允许把 `last_message_*` 推到更新的位置"""
    if not is_after(
        created_at=message.created_at,
        message_id=message.id,
        than_created_at=chat.last_message_at,
        than_message_id=chat.last_message_id,
    ):
        return False
    advance_last_message(
        session=session,
        chat=chat,
        message_id=message.id,
        created_at=message.created_at,
        preview=build_preview(
            message_type=message.message_type,
            content=message.content,
            file_name=message.file_name,
        ),
    )
    return True


def to_message_items(
    *,
    session: Session,
    messages: list[Message],
) -> list[MessagePublic]:
    """组装消息展示结构（附带发送者展示名）"""
    sender_ids = {
        message.sender_id
        for message in messages
        if message.sender_id is not None
    }
    users = load_users(session=session, user_ids=sender_ids)
    return [
        MessagePublic(
            id=message.id,
            chat_id=message.chat_id,
            sender_id=message.sender_id,
            sender_name=(
                user_display_name(users[message.sender_id])
                if message.sender_id in users
                else None
            ),
            message_type=message.message_type,
            content=message.content,
            file_name=message.file_name,
            file_path=message.file_path,
            client_message_id=message.client_message_id,
            created_at=message.created_at,
        )
        for message in messages
    ]
