"""聊天模块：聊天访问判定

两层权限：

1. 模块动作权限（`chat:*`）由 API 层 `require_permission` 校验，决定能否调用接口；
2. 数据级权限：群聊看 `ChatParticipant`（必须是成员）；
   私聊看 `direct_key`（会话属于确定的两个用户，成员关系是结构性的）。

私聊的成员行承担「是否显示在我的列表 + 已读游标」，所以删除会话（删除成员行）之后，
双方任何一方再次打开会话或对方发来新消息时都会自动补回成员行，历史消息也不会丢失。

无权限一律返回 **400**：前端把 403 视为登录态失效（清 token 跳登录页），
不适合表达「这条聊天你看不到」这类自助能力错误。
"""

import uuid

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.chat.domain.constants import (
    ChatType,
    ParticipantRole,
    parse_direct_key,
)
from app.modules.chat.models import Chat, ChatParticipant
from app.modules.chat.repositories.chat import get_chat
from app.modules.chat.repositories.participant import (
    add_participant,
    get_participant,
)
from app.modules.user.models import User


def get_accessible_chat(
    *,
    session: Session,
    user: User,
    chat_id: uuid.UUID,
) -> tuple[Chat, ChatParticipant]:
    """校验聊天访问权，返回聊天与当前用户的成员记录"""
    chat = get_chat(session=session, chat_id=chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="聊天不存在")
    participant = get_participant(
        session=session, chat_id=chat.id, user_id=user.id
    )
    if participant is None and is_direct_member(chat=chat, user_id=user.id):
        # 私聊：删除会话后重新打开时恢复成员行，位点按「已读到当前最后一条」处理
        participant = add_participant(
            session=session,
            chat_id=chat.id,
            user_id=user.id,
            role=ParticipantRole.MEMBER,
            last_read_message_id=chat.last_message_id,
        )
        session.commit()
        session.refresh(participant)
    if participant is None:
        raise HTTPException(status_code=400, detail="无权访问该聊天")
    return chat, participant


def is_direct_member(*, chat: Chat, user_id: uuid.UUID) -> bool:
    """私聊成员判定：用户 ID 是否落在 direct_key 里（与发起方向无关）"""
    if chat.type != ChatType.DIRECT or not chat.direct_key:
        return False
    return user_id in parse_direct_key(chat.direct_key)
