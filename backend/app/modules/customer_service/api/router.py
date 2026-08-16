"""客服模块：接口层"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.common.models import Message
from app.modules.customer_service.application.conversation_manage import (
    delete_conversation,
    get_or_create_conversation,
    list_conversations,
    to_conversation_public,
    update_conversation_status,
)
from app.modules.customer_service.application.message_manage import (
    get_messages,
    mark_conversation_read,
    send_message,
)
from app.modules.customer_service.schemas.conversation import (
    ConversationCreate,
    ConversationPublic,
    ConversationsPublic,
    ConversationStatusUpdate,
)
from app.modules.customer_service.schemas.message import (
    MessageCreate,
    MessagePublic,
    MessagesPublic,
    OnlineStatusPublic,
)
from app.modules.realtime.manager import batch_online
from app.modules.user.models import User

router = APIRouter(prefix="/customer-service", tags=["customer-service"])


@router.get("/conversations", response_model=ConversationsPublic)
def read_conversations(
    session: SessionDep,
    current_user: CurrentUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ConversationsPublic:
    """会话列表：管理端查全部，普通用户查自己的"""
    return list_conversations(
        session=session,
        current_user=current_user,
        skip=skip,
        limit=limit,
    )


@router.post("/conversations", response_model=ConversationPublic)
def create_conversation_endpoint(
    session: SessionDep,
    current_user: CurrentUser,
    body: ConversationCreate | None = None,
) -> ConversationPublic:
    """发起会话：普通用户获取自己的进行中会话；管理端为指定用户发起"""
    if current_user.is_superuser:
        if body is None or body.user_id is None:
            raise HTTPException(
                status_code=400,
                detail="管理端发起会话需指定用户",
            )
        target = session.get(User, body.user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="用户不存在")
        user_id = body.user_id
    else:
        if current_user.id is None:
            raise HTTPException(status_code=400, detail="用户 ID 缺失")
        user_id = current_user.id
    conversation = get_or_create_conversation(
        session=session,
        user_id=user_id,
    )
    return to_conversation_public(
        session=session,
        conversation=conversation,
        include_user_info=current_user.is_superuser,
        reader_id=current_user.id,
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessagesPublic,
)
def read_messages(
    session: SessionDep,
    current_user: CurrentUser,
    conversation_id: uuid.UUID,
    before: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> MessagesPublic:
    """分页查询会话消息（最新在前），before 为游标时返回其之前更早的消息"""
    return get_messages(
        session=session,
        conversation_id=conversation_id,
        user=current_user,
        limit=limit,
        before_id=before,
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessagePublic,
)
def send_message_endpoint(
    session: SessionDep,
    current_user: CurrentUser,
    conversation_id: uuid.UUID,
    body: MessageCreate,
) -> MessagePublic:
    """发送客服消息，并向会话参与者实时推送"""
    message = send_message(
        session=session,
        conversation_id=conversation_id,
        sender=current_user,
        content=body.content,
    )
    return MessagePublic.model_validate(message)


@router.post(
    "/conversations/{conversation_id}/read",
    response_model=ConversationPublic,
)
def read_conversation(
    session: SessionDep,
    current_user: CurrentUser,
    conversation_id: uuid.UUID,
) -> ConversationPublic:
    """标记会话中对方发来的消息为已读"""
    conversation = mark_conversation_read(
        session=session,
        conversation_id=conversation_id,
        reader=current_user,
    )
    return to_conversation_public(
        session=session,
        conversation=conversation,
        include_user_info=current_user.is_superuser,
        reader_id=current_user.id,
    )


@router.patch(
    "/conversations/{conversation_id}/status",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ConversationPublic,
)
def update_status_endpoint(
    session: SessionDep,
    current_user: CurrentUser,
    conversation_id: uuid.UUID,
    body: ConversationStatusUpdate,
) -> ConversationPublic:
    """管理端开关会话（open / closed）"""
    conversation = update_conversation_status(
        session=session,
        conversation_id=conversation_id,
        status=body.status,
    )
    return to_conversation_public(
        session=session,
        conversation=conversation,
        include_user_info=True,
        reader_id=current_user.id,
    )


@router.delete(
    "/conversations/{conversation_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def delete_conversation_endpoint(
    session: SessionDep,
    conversation_id: uuid.UUID,
) -> Message:
    """删除会话及其全部消息（仅管理端可删除）"""
    delete_conversation(
        session=session,
        conversation_id=conversation_id,
    )
    return Message(message="会话已删除")


@router.get(
    "/online",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=OnlineStatusPublic,
)
def read_online_status(
    user_ids: Annotated[list[uuid.UUID], Query()],
) -> OnlineStatusPublic:
    """管理端批量查询用户在线状态"""
    return OnlineStatusPublic(online=batch_online(user_ids))
