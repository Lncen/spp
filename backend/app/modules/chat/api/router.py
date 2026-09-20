"""聊天模块：聊天接口层

路由只做权限校验、参数接收与响应组装，业务规则在 application 层。

静态路径（`/unread-count`）必须声明在 `/{chat_id}` 之前，
否则会被当作 `chat_id` 解析并返回 422。
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, SessionDep, require_permission
from app.common.models import Message
from app.modules.chat.application.chat_manage import (
    add_chat_participant,
    create_group_chat,
    delete_chat_for_user,
    get_chat_detail,
    get_or_create_direct_chat,
    list_chat_participants,
    list_my_chats,
    remove_chat_participant,
)
from app.modules.chat.application.message_manage import list_chat_messages
from app.modules.chat.application.read_manage import (
    get_my_unread_count,
    mark_chat_read,
)
from app.modules.chat.domain.constants import (
    CHAT_CREATE_PERMISSION_CODE,
    CHAT_GROUP_CREATE_PERMISSION_CODE,
    CHAT_SELF_VIEW_PERMISSION_CODE,
    DEFAULT_MESSAGE_PAGE_SIZE,
    MAX_MESSAGE_PAGE_SIZE,
)
from app.modules.chat.schemas.chat import (
    ChatDirectCreate,
    ChatGroupCreate,
    ChatPublic,
    ChatReadBody,
    ChatReadResult,
    ChatsPublic,
    ChatUnreadCount,
)
from app.modules.chat.schemas.message import MessagesPublic
from app.modules.chat.schemas.participant import (
    ParticipantAdd,
    ParticipantsPublic,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get(
    "/",
    dependencies=[Depends(require_permission(CHAT_SELF_VIEW_PERMISSION_CODE))],
    response_model=ChatsPublic,
)
def read_my_chats(
    session: SessionDep,
    current_user: CurrentUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_MESSAGE_PAGE_SIZE)] = 50,
) -> ChatsPublic:
    """当前用户参与的聊天列表（最后消息时间倒序，含未读数）"""
    return list_my_chats(
        session=session,
        current_user=current_user,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/unread-count",
    dependencies=[Depends(require_permission(CHAT_SELF_VIEW_PERMISSION_CODE))],
    response_model=ChatUnreadCount,
)
def read_my_unread_count(
    session: SessionDep,
    current_user: CurrentUser,
) -> ChatUnreadCount:
    """当前用户全部聊天的未读消息总数（侧边栏聊天角标）"""
    return get_my_unread_count(session=session, current_user=current_user)


@router.post(
    "/direct",
    dependencies=[Depends(require_permission(CHAT_CREATE_PERMISSION_CODE))],
    response_model=ChatPublic,
)
def create_direct_chat(
    session: SessionDep,
    current_user: CurrentUser,
    body: ChatDirectCreate,
) -> ChatPublic:
    """创建或复用与指定用户的私聊（双向命中的同一条聊天）"""
    return get_or_create_direct_chat(
        session=session,
        current_user=current_user,
        other_user_id=body.user_id,
    )


@router.post(
    "/group",
    dependencies=[
        Depends(require_permission(CHAT_GROUP_CREATE_PERMISSION_CODE))
    ],
    response_model=ChatPublic,
)
def create_group(
    session: SessionDep,
    current_user: CurrentUser,
    body: ChatGroupCreate,
) -> ChatPublic:
    """创建群聊（创建者为群主）"""
    return create_group_chat(
        session=session,
        current_user=current_user,
        name=body.name,
        member_ids=body.member_ids,
    )


@router.get(
    "/{chat_id}",
    dependencies=[Depends(require_permission(CHAT_SELF_VIEW_PERMISSION_CODE))],
    response_model=ChatPublic,
)
def read_chat(
    session: SessionDep,
    current_user: CurrentUser,
    chat_id: uuid.UUID,
) -> ChatPublic:
    """聊天详情（仅可见自己参与的聊天）"""
    return get_chat_detail(
        session=session, current_user=current_user, chat_id=chat_id
    )


@router.get(
    "/{chat_id}/messages",
    dependencies=[Depends(require_permission(CHAT_SELF_VIEW_PERMISSION_CODE))],
    response_model=MessagesPublic,
)
def read_chat_messages(
    session: SessionDep,
    current_user: CurrentUser,
    chat_id: uuid.UUID,
    limit: Annotated[
        int, Query(ge=1, le=MAX_MESSAGE_PAGE_SIZE)
    ] = DEFAULT_MESSAGE_PAGE_SIZE,
    before: uuid.UUID | None = Query(
        default=None,
        title="游标消息 ID",
        description="返回该消息之前（更早）的一页",
    ),
) -> MessagesPublic:
    """按 `(created_at, id)` 游标分页查询消息（最新在前，不用 offset）"""
    return list_chat_messages(
        session=session,
        current_user=current_user,
        chat_id=chat_id,
        limit=limit,
        before_id=before,
    )


@router.post(
    "/{chat_id}/read",
    dependencies=[Depends(require_permission(CHAT_SELF_VIEW_PERMISSION_CODE))],
    response_model=ChatReadResult,
)
def mark_read(
    session: SessionDep,
    current_user: CurrentUser,
    chat_id: uuid.UUID,
    body: ChatReadBody,
) -> ChatReadResult:
    """把已读游标推进到指定消息（只向前，重复提交不会回退）"""
    return mark_chat_read(
        session=session,
        current_user=current_user,
        chat_id=chat_id,
        message_id=body.message_id,
    )


@router.get(
    "/{chat_id}/participants",
    dependencies=[Depends(require_permission(CHAT_SELF_VIEW_PERMISSION_CODE))],
    response_model=ParticipantsPublic,
)
def read_chat_participants(
    session: SessionDep,
    current_user: CurrentUser,
    chat_id: uuid.UUID,
) -> ParticipantsPublic:
    """聊天成员列表"""
    return list_chat_participants(
        session=session, current_user=current_user, chat_id=chat_id
    )


@router.post(
    "/{chat_id}/participants",
    dependencies=[Depends(require_permission(CHAT_SELF_VIEW_PERMISSION_CODE))],
    response_model=ParticipantsPublic,
)
def add_participant(
    session: SessionDep,
    current_user: CurrentUser,
    chat_id: uuid.UUID,
    body: ParticipantAdd,
) -> ParticipantsPublic:
    """把用户加入群聊（需群主或成员管理权限）"""
    return add_chat_participant(
        session=session,
        current_user=current_user,
        chat_id=chat_id,
        user_id=body.user_id,
        role=body.role,
    )


@router.delete(
    "/{chat_id}/participants/{user_id}",
    dependencies=[Depends(require_permission(CHAT_SELF_VIEW_PERMISSION_CODE))],
    response_model=ParticipantsPublic,
)
def delete_participant(
    session: SessionDep,
    current_user: CurrentUser,
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ParticipantsPublic:
    """把成员移出群聊（需群主或成员管理权限）"""
    return remove_chat_participant(
        session=session,
        current_user=current_user,
        chat_id=chat_id,
        user_id=user_id,
    )


@router.delete(
    "/{chat_id}",
    dependencies=[Depends(require_permission(CHAT_SELF_VIEW_PERMISSION_CODE))],
    response_model=Message,
)
def delete_chat(
    session: SessionDep,
    current_user: CurrentUser,
    chat_id: uuid.UUID,
) -> Message:
    """删除会话（仅自己不可见）：私聊移除自己的成员行，群聊为退出群聊（群主需先转让）"""
    delete_chat_for_user(
        session=session, current_user=current_user, chat_id=chat_id
    )
    return Message(message="聊天已删除")
