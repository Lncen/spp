"""客服模块：消息应用服务（发送 / 查询 / 已读）"""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.modules.customer_service.application.conversation_manage import (
    list_active_superuser_ids,
    to_conversation_public,
)
from app.modules.customer_service.application.realtime_publish import (
    conversation_participant_ids,
    publish_message_created,
    publish_message_read,
)
from app.modules.customer_service.domain.constants import SenderRole
from app.modules.customer_service.models import Conversation, ConversationMessage
from app.modules.customer_service.repositories.conversation import (
    get_conversation,
    touch_conversation,
)
from app.modules.customer_service.repositories.message import (
    create_message,
    list_messages,
    mark_messages_read,
)
from app.modules.customer_service.schemas.message import (
    MessagePublic,
    MessagesPublic,
)
from app.modules.user.models import User


def is_participant(
    *,
    conversation: Conversation,
    user: User,
) -> bool:
    """会话参与者校验：本人或管理员"""
    return user.is_superuser or (
        conversation.user_id is not None
        and user.id is not None
        and conversation.user_id == user.id
    )


def _get_participant_conversation(
    *,
    session: Session,
    conversation_id: uuid.UUID,
    user: User,
) -> Conversation:
    """获取会话并校验当前用户是参与者"""
    conversation = get_conversation(
        session=session, conversation_id=conversation_id
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if not is_participant(conversation=conversation, user=user):
        raise HTTPException(status_code=403, detail="无权访问该会话")
    return conversation


def send_message(
    *,
    session: Session,
    conversation_id: uuid.UUID,
    sender: User,
    content: str,
) -> ConversationMessage:
    """发送客服消息：落库后向会话参与者实时推送"""
    conversation = _get_participant_conversation(
        session=session,
        conversation_id=conversation_id,
        user=sender,
    )
    if conversation.status != "open":
        raise HTTPException(status_code=400, detail="会话已关闭，无法发送消息")
    if sender.id is None:
        raise HTTPException(status_code=400, detail="用户 ID 缺失")
    sender_role = SenderRole.ADMIN if sender.is_superuser else SenderRole.USER
    now = datetime.now(UTC)
    message = create_message(
        session=session,
        conversation_id=conversation.id,
        sender_id=sender.id,
        sender_role=sender_role,
        content=content,
    )
    touch_conversation(
        conversation=conversation,
        now=now,
        preview=content,
    )
    session.add(conversation)
    session.commit()
    session.refresh(message)

    admin_ids = list_active_superuser_ids(session=session)
    publish_message_created(
        participant_ids=conversation_participant_ids(
            conversation=conversation,
            admin_ids=admin_ids,
        ),
        message=message,
    )
    return message


def get_messages(
    *,
    session: Session,
    conversation_id: uuid.UUID,
    user: User,
    limit: int,
    before_id: uuid.UUID | None = None,
) -> MessagesPublic:
    """分页查询会话消息（最新在前），附带会话信息与消息总数"""
    conversation = _get_participant_conversation(
        session=session,
        conversation_id=conversation_id,
        user=user,
    )
    messages = list_messages(
        session=session,
        conversation_id=conversation.id,
        limit=limit,
        before_id=before_id,
    )
    total = session.exec(
        select(func.count())
        .select_from(ConversationMessage)
        .where(col(ConversationMessage.conversation_id) == conversation.id)
    ).one()
    conversation_public = to_conversation_public(
        session=session,
        conversation=conversation,
        include_user_info=user.is_superuser,
        reader_id=user.id,
    )
    return MessagesPublic(
        data=[
            MessagePublic.model_validate(message)
            for message in messages
        ],
        count=total,
        conversation=conversation_public,
    )


def mark_conversation_read(
    *,
    session: Session,
    conversation_id: uuid.UUID,
    reader: User,
) -> Conversation:
    """标记会话中他人发来的消息为已读，并实时通知对方"""
    conversation = _get_participant_conversation(
        session=session,
        conversation_id=conversation_id,
        user=reader,
    )
    reader_role = SenderRole.ADMIN if reader.is_superuser else SenderRole.USER
    updated = mark_messages_read(
        session=session,
        conversation_id=conversation.id,
        reader_id=reader.id,
        now=datetime.now(UTC),
    )
    session.commit()
    if updated:
        admin_ids = list_active_superuser_ids(session=session)
        publish_message_read(
            participant_ids=conversation_participant_ids(
                conversation=conversation,
                admin_ids=admin_ids,
            ),
            conversation_id=conversation.id,
            reader_role=reader_role,
        )
    session.refresh(conversation)
    return conversation
