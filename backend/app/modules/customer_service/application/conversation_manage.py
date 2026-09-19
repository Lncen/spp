"""客服模块：会话应用服务（创建 / 查询 / 状态管理）"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session, col, select

from app.modules.authorization.application.permission_check import (
    has_permission,
    list_active_user_ids_with_permission,
)
from app.modules.customer_service.application.realtime_publish import (
    conversation_participant_ids,
    publish_conversation_deleted,
)
from app.modules.customer_service.domain.constants import (
    CONVERSATION_SELF_VIEW_PERMISSION_CODE,
    CONVERSATION_VIEW_PERMISSION_CODE,
    ConversationStatus,
)
from app.modules.customer_service.models import Conversation, ConversationMessage
from app.modules.customer_service.repositories.conversation import (
    count_unread_messages,
    count_unread_total,
    create_conversation,
    get_conversation,
    get_open_conversation_by_user,
    list_all_conversations,
    list_conversations_by_user,
    lock_conversation_owner,
    set_conversation_status,
)
from app.modules.customer_service.schemas.conversation import (
    ConversationPublic,
    ConversationsPublic,
)
from app.modules.image.infrastructure.image_storage import build_image_url
from app.modules.image.models import Image
from app.modules.realtime.manager import batch_online
from app.modules.user.models import User


def _user_display_name(user: User) -> str:
    """展示名：昵称 → 用户名 → 邮箱，均为空时回退为 用户 + ID 后 6 位"""
    return user.full_name or user.username or user.email or f"用户{str(user.id)[-6:]}"


def _user_avatar_urls(
    *, session: Session, users: dict[uuid.UUID, User]
) -> dict[uuid.UUID, str]:
    """批量组装用户头像 URL（未设置头像或图片已删除的用户不返回）"""
    avatar_ids = {user.avatar_id for user in users.values() if user.avatar_id}
    if not avatar_ids:
        return {}
    paths = {
        image.id: image.file_path
        for image in session.exec(
            select(Image).where(col(Image.id).in_(avatar_ids))
        ).all()
    }
    return {
        user_id: build_image_url(paths[user.avatar_id])
        for user_id, user in users.items()
        if user.avatar_id is not None and user.avatar_id in paths
    }


def is_agent(*, session: Session, user: User) -> bool:
    """是否客服坐席：持有「查看全部会话」权限码即为接待方，超级管理员天然持有"""
    return has_permission(
        session=session, user=user, code=CONVERSATION_VIEW_PERMISSION_CODE
    )


def _latest_other_sender_names(
    *,
    session: Session,
    conversation_ids: list[uuid.UUID],
    reader_id: uuid.UUID,
) -> dict[uuid.UUID, str]:
    """各会话中最近一条他人发来消息的发送者展示名（昵称 → 用户名 → 邮箱）"""
    names: dict[uuid.UUID, str] = {}
    if not conversation_ids:
        return names
    rows = session.exec(
        select(ConversationMessage.conversation_id, User)
        .join(User, User.id == ConversationMessage.sender_id)
        .where(
            col(ConversationMessage.conversation_id).in_(conversation_ids),
            col(ConversationMessage.sender_id) != reader_id,
        )
        .order_by(
            ConversationMessage.created_at.desc(),
            ConversationMessage.id.desc(),
        )
    ).all()
    for conversation_id, sender in rows:
        if conversation_id not in names:
            names[conversation_id] = _user_display_name(sender)
    return names


def get_total_conversation_unread(*, session: Session, user: User) -> int:
    """当前查看者可见会话中他人发来且未读的消息总数（侧边栏角标汇总用，客服坐席统计全部会话）

    未持有会话查看权限（自助查看或坐席查看）时返回 0，
    避免侧边栏角标向无会话权限的账号暴露会话未读数。
    """
    if user.id is None:
        return 0
    can_view_all = is_agent(session=session, user=user)
    if not can_view_all and not has_permission(
        session=session, user=user, code=CONVERSATION_SELF_VIEW_PERMISSION_CODE
    ):
        return 0
    return count_unread_total(
        session=session,
        user_id=user.id,
        can_view_all=can_view_all,
    )


def list_active_agent_ids(*, session: Session) -> list[uuid.UUID]:
    """当前启用的客服坐席 ID 列表（会话接待方）"""
    return list_active_user_ids_with_permission(
        session=session, code=CONVERSATION_VIEW_PERMISSION_CODE
    )


def get_or_create_conversation(
    *,
    session: Session,
    user_id: uuid.UUID,
) -> Conversation:
    """获取用户的进行中会话，不存在则创建（用户联系客服 / 管理端主动联系共用）

    先对用户行加排他锁（``lock_conversation_owner``）再查询/创建，
    避免同一用户的并发请求各建一条进行中会话；命中已有会话时显式提交，
    让事务立即结束、尽快释放行锁，不把锁持有到请求结束。
    """
    lock_conversation_owner(session=session, user_id=user_id)
    existing = get_open_conversation_by_user(session=session, user_id=user_id)
    if existing:
        session.commit()
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
    """会话列表：客服坐席查全部，普通用户查自己的"""
    can_view_all = is_agent(session=session, user=current_user)
    if can_view_all:
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
            include_user_info=can_view_all,
            reader_id=current_user.id,
        ),
        count=count,
    )


def to_conversation_public(
    *,
    session: Session,
    conversation: Conversation,
    include_user_info: bool,
    reader_id: uuid.UUID,
) -> ConversationPublic:
    """单条会话展示结构"""
    return _to_conversation_items(
        session=session,
        conversations=[conversation],
        include_user_info=include_user_info,
        reader_id=reader_id,
    )[0]


def _to_conversation_items(
    *,
    session: Session,
    conversations: list[Conversation],
    include_user_info: bool,
    reader_id: uuid.UUID,
) -> list[ConversationPublic]:
    """组装会话展示结构列表；管理端附带用户展示名与在线状态"""
    user_ids = {
        conversation.user_id
        for conversation in conversations
        if conversation.user_id is not None
    }
    users: dict[uuid.UUID, User] = {}
    online: dict[str, bool] = {}
    avatar_urls: dict[uuid.UUID, str] = {}
    if include_user_info and user_ids:
        users = {
            user.id: user
            for user in session.exec(
                select(User).where(col(User.id).in_(user_ids))
            ).all()
            if user.id is not None
        }
        online = batch_online(list(user_ids))
        avatar_urls = _user_avatar_urls(session=session, users=users)

    conversation_ids = [
        conversation.id
        for conversation in conversations
        if conversation.id is not None
    ]
    owner_conversation_ids = [
        conversation.id
        for conversation in conversations
        if conversation.id is not None
        and conversation.user_id is not None
        and conversation.user_id == reader_id
    ]
    counterpart_names = _latest_other_sender_names(
        session=session,
        conversation_ids=owner_conversation_ids,
        reader_id=reader_id,
    )
    unread_counts = count_unread_messages(
        session=session,
        conversation_ids=conversation_ids,
        reader_id=reader_id,
    )

    items: list[ConversationPublic] = []
    for conversation in conversations:
        if (
            conversation.user_id is not None
            and conversation.user_id == reader_id
        ):
            user_name = counterpart_names.get(conversation.id, "客服")
            user_avatar_url = None
        else:
            user = users.get(conversation.user_id) if conversation.user_id else None
            user_name = _user_display_name(user) if user else None
            user_avatar_url = (
                avatar_urls.get(conversation.user_id) if conversation.user_id else None
            )
        items.append(
            ConversationPublic(
                id=conversation.id,
                user_id=conversation.user_id,
                status=conversation.status,
                last_message_at=conversation.last_message_at,
                last_message_preview=conversation.last_message_preview,
                created_at=conversation.created_at,
                user_name=user_name,
                user_avatar_url=user_avatar_url,
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

    agent_ids = list_active_agent_ids(session=session)
    participant_ids = conversation_participant_ids(
        conversation=conversation,
        agent_ids=agent_ids,
    )
    session.delete(conversation)
    session.commit()
    publish_conversation_deleted(
        participant_ids=participant_ids,
        conversation_id=conversation_id,
    )
