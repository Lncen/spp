"""客服模块：会话应用服务（创建 / 查询 / 状态管理）"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.modules.customer_service.application.realtime_publish import (
    conversation_participant_ids,
    publish_conversation_deleted,
)
from app.modules.customer_service.domain.constants import (
    ConversationStatus,
    SenderRole,
)
from app.modules.customer_service.models import Conversation
from app.modules.customer_service.repositories.conversation import (
    count_unread_messages,
    count_unread_total,
    create_conversation,
    get_conversation,
    get_open_conversation_by_user,
    list_all_conversations,
    list_conversations_by_user,
    set_conversation_status,
)
from app.modules.customer_service.schemas.conversation import (
    ConversationPublic,
    ConversationsPublic,
)
from app.modules.realtime.manager import batch_online
from app.modules.user.models import User


def _user_display_name(user: User) -> str:
    """接收对象展示名：全名 > 用户名 > 邮箱"""
    return user.full_name or user.username or user.email


def reader_role_for(user: User) -> str:
    """当前查看者角色（未读消息按对方角色统计）"""
    return SenderRole.ADMIN if user.is_superuser else SenderRole.USER


def get_total_conversation_unread(*, session: Session, user: User) -> int:
    """当前查看者全部会话的未读消息总数（侧边栏角标汇总用）"""
    if user.id is None:
        return 0
    return count_unread_total(
        session=session,
        user_id=user.id,
        is_superuser=user.is_superuser,
        reader_role=reader_role_for(user),
    )


def list_active_superuser_ids(*, session: Session) -> list[uuid.UUID]:
    """当前启用的管理员 ID 列表（客服接待方）"""
    return [
        user.id
        for user in session.exec(
            select(User).where(
                col(User.is_superuser).is_(True),
                col(User.is_active).is_(True),
            )
        ).all()
        if user.id is not None
    ]


def get_or_create_conversation(
    *,
    session: Session,
    user_id: uuid.UUID,
) -> Conversation:
    """获取用户的进行中会话，不存在则创建（用户联系客服 / 管理端主动联系共用）"""
    existing = get_open_conversation_by_user(session=session, user_id=user_id)
    if existing:
        return existing
    conversation = create_conversation(session=session, user_id=user_id)
    session.commit()
    session.refresh(conversation)
    return conversation


def list_conversations(
    *,
    session: Session,
    current_user: User,
    skip: int,
    limit: int,
) -> ConversationsPublic:
    """会话列表：管理端查全部，普通用户查自己的"""
    if current_user.is_superuser:
        count, conversations = list_all_conversations(
            session=session, skip=skip, limit=limit
        )
    else:
        if current_user.id is None:
            raise HTTPException(status_code=400, detail="用户 ID 缺失")
        count, conversations = list_conversations_by_user(
            session=session,
            user_id=current_user.id,
            skip=skip,
            limit=limit,
        )
    return ConversationsPublic(
        data=_to_conversation_items(
            session=session,
            conversations=conversations,
            include_user_info=current_user.is_superuser,
            reader_role=reader_role_for(current_user),
        ),
        count=count,
    )


def to_conversation_public(
    *,
    session: Session,
    conversation: Conversation,
    include_user_info: bool,
    reader_role: str,
) -> ConversationPublic:
    """单条会话展示结构"""
    return _to_conversation_items(
        session=session,
        conversations=[conversation],
        include_user_info=include_user_info,
        reader_role=reader_role,
    )[0]


def _to_conversation_items(
    *,
    session: Session,
    conversations: list[Conversation],
    include_user_info: bool,
    reader_role: str,
) -> list[ConversationPublic]:
    """组装会话展示结构列表；管理端附带用户展示名与在线状态"""
    user_ids = {
        conversation.user_id
        for conversation in conversations
        if conversation.user_id is not None
    }
    users: dict[uuid.UUID, User] = {}
    online: dict[str, bool] = {}
    if include_user_info and user_ids:
        users = {
            user.id: user
            for user in session.exec(
                select(User).where(col(User.id).in_(user_ids))
            ).all()
            if user.id is not None
        }
        online = batch_online(list(user_ids))

    conversation_ids = [
        conversation.id
        for conversation in conversations
        if conversation.id is not None
    ]
    unread_counts = count_unread_messages(
        session=session,
        conversation_ids=conversation_ids,
        reader_role=reader_role,
    )

    items: list[ConversationPublic] = []
    for conversation in conversations:
        user = users.get(conversation.user_id) if conversation.user_id else None
        items.append(
            ConversationPublic(
                id=conversation.id,
                user_id=conversation.user_id,
                status=conversation.status,
                last_message_at=conversation.last_message_at,
                last_message_preview=conversation.last_message_preview,
                created_at=conversation.created_at,
                user_name=_user_display_name(user) if user else None,
                user_online=(
                    online.get(str(conversation.user_id), False)
                    if conversation.user_id
                    else False
                ),
                unread_count=unread_counts.get(conversation.id, 0),
            )
        )
    return items


def update_conversation_status(
    *,
    session: Session,
    conversation_id: uuid.UUID,
    status: str,
) -> Conversation:
    """管理端更新会话状态（open / closed）"""
    if status not in (ConversationStatus.OPEN, ConversationStatus.CLOSED):
        raise HTTPException(status_code=400, detail="无效的会话状态")
    conversation = get_conversation(
        session=session, conversation_id=conversation_id
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    set_conversation_status(conversation=conversation, status=status)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def delete_conversation(
    *,
    session: Session,
    conversation_id: uuid.UUID,
) -> None:
    """删除会话及其全部消息（级联），并实时通知参与者（仅管理端调用）"""
    conversation = get_conversation(
        session=session, conversation_id=conversation_id
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    admin_ids = list_active_superuser_ids(session=session)
    participant_ids = conversation_participant_ids(
        conversation=conversation,
        admin_ids=admin_ids,
    )
    session.delete(conversation)
    session.commit()
    publish_conversation_deleted(
        participant_ids=participant_ids,
        conversation_id=conversation_id,
    )
