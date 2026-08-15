"""客服模块：实时会话守卫注册（依赖倒置）

realtime 是叶子基础设施，不依赖业务模块；
本文件在应用启动时注册「会话参与者」查询回调，供 Socket.IO typing 事件校验使用。
"""

import logging
import uuid

from sqlmodel import Session, col, select

from app.core.db import engine
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
        if not (user.is_superuser or conversation.user_id == user.id):
            return None
        admins = session.exec(
            select(User).where(
                col(User.is_superuser).is_(True),
                col(User.is_active).is_(True),
            )
        ).all()
        return [
            conversation.user_id,
            *(admin.id for admin in admins if admin.id is not None),
        ]


register_conversation_participants(_conversation_participant_ids)
logger.info("客服实时会话守卫已注册")
