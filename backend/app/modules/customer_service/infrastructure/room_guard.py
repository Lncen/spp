"""客服模块：实时会话守卫注册（依赖倒置）

realtime 是叶子基础设施，不依赖业务模块；
本文件在应用启动时注册「会话参与者」查询回调，供 Socket.IO typing 事件校验使用。
"""

import logging
import uuid

from sqlmodel import Session

from app.core.db import engine
from app.modules.authorization.application.permission_check import (
    has_permission,
    list_active_user_ids_with_permission,
)
from app.modules.customer_service.domain.constants import (
    CONVERSATION_VIEW_PERMISSION_CODE,
)
from app.modules.customer_service.models import Conversation
from app.modules.realtime.server import register_conversation_participants
from app.modules.user.models import User

logger = logging.getLogger(__name__)


def _conversation_participant_ids(
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> list[uuid.UUID] | None:
    """返回会话参与者 ID；非参与者返回 None（拒绝）"""
    with Session(engine) as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            return None
        user = session.get(User, user_id)
        if user is None:
            return None
        is_owner = conversation.user_id == user.id
        if not (
            is_owner
            or has_permission(
                session=session, user=user, code=CONVERSATION_VIEW_PERMISSION_CODE
            )
        ):
            return None
        return [
            conversation.user_id,
            *list_active_user_ids_with_permission(
                session=session, code=CONVERSATION_VIEW_PERMISSION_CODE
            ),
        ]


register_conversation_participants(_conversation_participant_ids)
logger.info("客服实时会话守卫已注册")
