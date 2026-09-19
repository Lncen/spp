"""客服模块：消息应用服务（发送 / 查询 / 已读）"""

import uuid

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.time import get_datetime_cn
from app.modules.authorization.application.permission_check import has_permission
from app.modules.customer_service.application.conversation_manage import (
    is_agent,
    list_active_agent_ids,
    to_conversation_public,
)
from app.modules.customer_service.application.realtime_publish import (
    conversation_participant_ids,
    publish_message_created,
    publish_message_read,
)
from app.modules.customer_service.domain.constants import (
    CONVERSATION_REPLY_PERMISSION_CODE,
    SenderRole,
)
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


def _is_conversation_owner(*, conversation: Conversation, user: User) -> bool:
    """是否会话所属用户本人"""
    return (
        conversation.user_id is not None
        and user.id is not None
        and conversation.user_id == user.id
    )


def is_participant(
    *,
    session: Session,
    conversation: Conversation,
    user: User,
) -> bool:
    """会话参与者校验：会话本人或客服坐席（持有查看全部会话权限）"""
    return _is_conversation_owner(conversation=conversation, user=user) or is_agent(
        session=session, user=user
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
    if not is_participant(
        session=session, conversation=conversation, user=user
    ):
        # 无权限访问按业务性拒绝返回 400：403 会被前端当作登录态失效处理
        raise HTTPException(status_code=400, detail="无权访问该会话")
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
    # 发送规则：会话参与者（会话本人或接待方坐席）持有「回复会话」权限码时才能发送；
    # 非参与者已由 _get_participant_conversation 拦截（400 无权访问该会话）
    if not has_permission(
        session=session, user=sender, code=CONVERSATION_REPLY_PERMISSION_CODE
    ):
        raise HTTPException(status_code=400, detail="无回复会话权限")
    sender_role = (
        SenderRole.ADMIN
        if is_agent(session=session, user=sender)
        else SenderRole.USER
    )
    now = get_datetime_cn()
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

    agent_ids = list_active_agent_ids(session=session)
    publish_message_created(
        participant_ids=conversation_participant_ids(
            conversation=conversation,
            agent_ids=agent_ids,
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
        include_user_info=is_agent(session=session, user=user),
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
    reader_role = (
        SenderRole.ADMIN
        if is_agent(session=session, user=reader)
        else SenderRole.USER
    )
    updated = mark_messages_read(
        session=session,
        conversation_id=conversation.id,
        reader_id=reader.id,
        now=get_datetime_cn(),
    )
    session.commit()
    if updated:
        agent_ids = list_active_agent_ids(session=session)
        publish_message_read(
            participant_ids=conversation_participant_ids(
                conversation=conversation,
                agent_ids=agent_ids,
            ),
            conversation_id=conversation.id,
            reader_role=reader_role,
        )
    session.refresh(conversation)
    return conversation
