"""聊天模块：聊天管理应用服务（创建 / 查询 / 成员维护）"""

import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.modules.authorization.application.permission_check import has_permission
from app.modules.chat.application.access import get_accessible_chat
from app.modules.chat.domain.constants import (
    CHAT_PARTICIPANT_MANAGE_PERMISSION_CODE,
    ChatType,
    ParticipantRole,
    build_direct_key,
)
from app.modules.chat.models import Chat, ChatParticipant
from app.modules.chat.repositories.chat import (
    create_chat,
    get_direct_chat,
    list_chats_for_user,
)
from app.modules.chat.repositories.participant import (
    add_participant,
    count_unread_by_chat,
    delete_participant,
    get_participant,
    list_participants,
)
from app.modules.chat.schemas.chat import ChatPublic, ChatsPublic
from app.modules.chat.schemas.participant import (
    ParticipantPublic,
    ParticipantsPublic,
)
from app.modules.realtime.manager import batch_online
from app.modules.user.application.user_display import (
    load_users,
    user_avatar_urls,
    user_display_name,
)
from app.modules.user.models import User

# 私聊创建发生唯一键冲突时的重试次数（对方事务提交后即可复用同一条聊天）
_DIRECT_CREATE_ATTEMPTS = 2


def list_my_chats(
    *,
    session: Session,
    current_user: User,
    skip: int,
    limit: int,
) -> ChatsPublic:
    """当前用户参与的聊天列表（最后消息时间倒序）"""
    count, chats = list_chats_for_user(
        session=session,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    return ChatsPublic(
        data=_to_chat_items(session=session, chats=chats, reader=current_user),
        count=count,
    )


def get_chat_detail(
    *,
    session: Session,
    current_user: User,
    chat_id: uuid.UUID,
) -> ChatPublic:
    """聊天详情（含未读数与展示名）"""
    chat, _ = get_accessible_chat(
        session=session, user=current_user, chat_id=chat_id
    )
    return _to_chat_items(session=session, chats=[chat], reader=current_user)[0]


def get_or_create_direct_chat(
    *,
    session: Session,
    current_user: User,
    other_user_id: uuid.UUID,
) -> ChatPublic:
    """创建或复用与指定用户的私聊（双向命中同一条聊天）"""
    if other_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能与自己创建私聊")
    other = session.get(User, other_user_id)
    if other is None or not other.is_active:
        raise HTTPException(status_code=404, detail="对方用户不存在或已停用")

    direct_key = build_direct_key(current_user.id, other_user_id)
    for _ in range(_DIRECT_CREATE_ATTEMPTS):
        existing = get_direct_chat(session=session, direct_key=direct_key)
        if existing is not None:
            return _to_chat_items(
                session=session, chats=[existing], reader=current_user
            )[0]
        try:
            chat = create_chat(
                session=session,
                chat_type=ChatType.DIRECT,
                direct_key=direct_key,
            )
            session.flush()
            add_participant(
                session=session,
                chat_id=chat.id,
                user_id=current_user.id,
                role=ParticipantRole.MEMBER,
            )
            add_participant(
                session=session,
                chat_id=chat.id,
                user_id=other_user_id,
                role=ParticipantRole.MEMBER,
            )
            session.commit()
        except IntegrityError:
            # 并发创建命中 direct_key 唯一约束：回滚后复用对方已创建的聊天
            session.rollback()
            continue
        session.refresh(chat)
        return _to_chat_items(
            session=session, chats=[chat], reader=current_user
        )[0]
    raise HTTPException(status_code=409, detail="私聊创建冲突，请重试")


def create_group_chat(
    *,
    session: Session,
    current_user: User,
    name: str,
    member_ids: list[uuid.UUID],
) -> ChatPublic:
    """创建群聊：创建者为 OWNER，其余成员为 MEMBER"""
    chat = create_chat(
        session=session,
        chat_type=ChatType.GROUP,
        name=name,
    )
    session.flush()
    add_participant(
        session=session,
        chat_id=chat.id,
        user_id=current_user.id,
        role=ParticipantRole.OWNER,
    )
    for user_id in dict.fromkeys(member_ids):
        if user_id == current_user.id:
            continue
        if session.get(User, user_id) is None:
            raise HTTPException(status_code=404, detail="成员用户不存在")
        add_participant(
            session=session,
            chat_id=chat.id,
            user_id=user_id,
            role=ParticipantRole.MEMBER,
        )
    session.commit()
    session.refresh(chat)
    return _to_chat_items(session=session, chats=[chat], reader=current_user)[0]


def list_chat_participants(
    *,
    session: Session,
    current_user: User,
    chat_id: uuid.UUID,
) -> ParticipantsPublic:
    """聊天成员列表"""
    chat, _ = get_accessible_chat(
        session=session, user=current_user, chat_id=chat_id
    )
    participants = list_participants(session=session, chat_id=chat.id)
    users = load_users(
        session=session,
        user_ids={item.user_id for item in participants},
    )
    avatars = user_avatar_urls(session=session, users=users)
    online: dict[str, bool] = batch_online([item.user_id for item in participants])
    data = [
        _to_participant_public(
            participant=item,
            users=users,
            avatars=avatars,
            online=online,
        )
        for item in participants
    ]
    return ParticipantsPublic(data=data, count=len(data))


def add_chat_participant(
    *,
    session: Session,
    current_user: User,
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str | None = None,
) -> ParticipantsPublic:
    """把用户加入聊天（群聊需群主身份）"""
    chat, _ = get_accessible_chat(
        session=session, user=current_user, chat_id=chat_id
    )
    _ensure_participant_manager(
        session=session, chat=chat, current_user=current_user
    )
    if session.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if get_participant(session=session, chat_id=chat.id, user_id=user_id):
        raise HTTPException(status_code=400, detail="该用户已在聊天中")
    if role is None:
        role = ParticipantRole.MEMBER
    add_participant(
        session=session,
        chat_id=chat.id,
        user_id=user_id,
        role=role,
    )
    session.commit()
    return list_chat_participants(
        session=session, current_user=current_user, chat_id=chat.id
    )


def remove_chat_participant(
    *,
    session: Session,
    current_user: User,
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ParticipantsPublic:
    """把成员移出聊天（仅群聊，需群主身份）"""
    chat, _ = get_accessible_chat(
        session=session, user=current_user, chat_id=chat_id
    )
    _ensure_participant_manager(
        session=session, chat=chat, current_user=current_user
    )
    participant = get_participant(
        session=session, chat_id=chat.id, user_id=user_id
    )
    if participant is None:
        raise HTTPException(status_code=404, detail="该用户不在聊天中")
    delete_participant(session=session, participant=participant)
    session.commit()
    return list_chat_participants(
        session=session, current_user=current_user, chat_id=chat.id
    )


def delete_chat_for_user(
    *,
    session: Session,
    current_user: User,
    chat_id: uuid.UUID,
) -> None:
    """删除会话（仅影响自己）：

    - 私聊：删除自己的成员行，会话从我的列表移除；对方不受影响，
      对方再发消息或我重新打开时会自动恢复（历史消息保留）；
    - 群聊：退出群聊，群主需先转让。
    """
    chat, participant = get_accessible_chat(
        session=session, user=current_user, chat_id=chat_id
    )
    if chat.type == ChatType.GROUP and participant.role == ParticipantRole.OWNER:
        raise HTTPException(
            status_code=400, detail="群主不能直接删除群聊，请先转让群主"
        )
    delete_participant(session=session, participant=participant)
    session.commit()


def _ensure_participant_manager(
    *,
    session: Session,
    chat: Chat,
    current_user: User,
) -> None:
    """成员管理校验：仅群聊可管理成员，群主或持有成员管理权限的人可操作"""
    if chat.type != ChatType.GROUP:
        raise HTTPException(status_code=400, detail="私聊不支持成员管理")
    if has_permission(
        session=session,
        user=current_user,
        code=CHAT_PARTICIPANT_MANAGE_PERMISSION_CODE,
    ):
        return
    participant = get_participant(
        session=session, chat_id=chat.id, user_id=current_user.id
    )
    if participant is None or participant.role != ParticipantRole.OWNER:
        raise HTTPException(status_code=400, detail="仅群主可管理群成员")


def _resolve_other_user_ids(
    *,
    session: Session,
    chats: list[Chat],
    reader: User,
) -> dict[uuid.UUID, uuid.UUID]:
    """解析每条一对一聊天的「对方」用户（群聊不展示对方）"""
    other_user_ids: dict[uuid.UUID, uuid.UUID] = {}
    one_to_one_chat_ids = [
        chat.id for chat in chats if chat.type != ChatType.GROUP
    ]
    if one_to_one_chat_ids:
        rows = session.exec(
            select(ChatParticipant.chat_id, ChatParticipant.user_id).where(
                col(ChatParticipant.chat_id).in_(one_to_one_chat_ids),
                col(ChatParticipant.user_id) != reader.id,
            )
        ).all()
        for chat_id, user_id in rows:
            other_user_ids[chat_id] = user_id
    return other_user_ids


def _to_participant_public(
    *,
    participant: ChatParticipant,
    users: dict[uuid.UUID, User],
    avatars: dict[uuid.UUID, str],
    online: dict[str, bool],
) -> ParticipantPublic:
    """成员展示结构"""
    user = users.get(participant.user_id)
    return ParticipantPublic(
        id=participant.id,
        user_id=participant.user_id,
        role=participant.role,
        display_name=user_display_name(user) if user else None,
        display_avatar_url=avatars.get(participant.user_id),
        is_online=online.get(str(participant.user_id), False),
        joined_at=participant.joined_at,
        last_read_message_id=participant.last_read_message_id,
    )


def _to_chat_items(
    *,
    session: Session,
    chats: list[Chat],
    reader: User,
) -> list[ChatPublic]:
    """组装聊天展示结构：展示名、头像与未读数"""
    if not chats:
        return []
    chat_ids = [chat.id for chat in chats]
    unread_counts = count_unread_by_chat(
        session=session, user_id=reader.id, chat_ids=chat_ids
    )
    other_user_ids = _resolve_other_user_ids(
        session=session, chats=chats, reader=reader
    )
    users = load_users(
        session=session, user_ids=set(other_user_ids.values())
    )
    avatars = user_avatar_urls(session=session, users=users)

    items: list[ChatPublic] = []
    for chat in chats:
        other_user_id = other_user_ids.get(chat.id)
        other_user = users.get(other_user_id) if other_user_id else None
        if chat.type == ChatType.GROUP:
            display_name = chat.name
            display_avatar_url = None
        else:
            display_name = (
                user_display_name(other_user) if other_user else None
            )
            display_avatar_url = avatars.get(other_user_id)
        items.append(
            ChatPublic(
                id=chat.id,
                type=chat.type,
                status=chat.status,
                name=chat.name,
                display_name=display_name,
                display_avatar_url=display_avatar_url,
                last_message_preview=chat.last_message_preview,
                last_message_at=chat.last_message_at,
                unread_count=unread_counts.get(chat.id, 0),
                created_at=chat.created_at,
            )
        )
    return items
