"""客服模块：消息实时发布（best-effort）

实时通道只是提醒，PostgreSQL 中的消息才是事实来源；
发布失败不影响消息落库，前端可重新拉取兜底。
"""

import logging
import uuid

from app.modules.customer_service.models import Conversation, ConversationMessage
from app.modules.realtime.events import RealtimeEvent
from app.modules.realtime.publisher import publish_to_users

logger = logging.getLogger(__name__)


def _message_payload(message: ConversationMessage) -> dict:
    """消息实时事件载荷（与 MessagePublic 字段一致）"""
    return {
        "id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "sender_id": str(message.sender_id) if message.sender_id else None,
        "sender_role": message.sender_role,
        "content": message.content,
        "read_at": (
            message.read_at.isoformat() if message.read_at is not None else None
        ),
        "created_at": (
            message.created_at.isoformat()
            if message.created_at is not None
            else None
        ),
    }


def publish_message_created(
    *,
    participant_ids: list[uuid.UUID],
    message: ConversationMessage,
) -> None:
    """向会话参与者推送 message.created"""
    publish_to_users(
        participant_ids,
        RealtimeEvent.CUSTOMER_SERVICE_MESSAGE_CREATED,
        _message_payload(message),
    )


def publish_message_read(
    *,
    participant_ids: list[uuid.UUID],
    conversation_id: uuid.UUID,
    reader_role: str,
) -> None:
    """向会话参与者推送 message.read"""
    publish_to_users(
        participant_ids,
        RealtimeEvent.CUSTOMER_SERVICE_MESSAGE_READ,
        {
            "conversation_id": str(conversation_id),
            "reader_role": reader_role,
        },
    )


def publish_conversation_deleted(
    *,
    participant_ids: list[uuid.UUID],
    conversation_id: uuid.UUID,
) -> None:
    """向会话参与者推送 conversation.deleted"""
    publish_to_users(
        participant_ids,
        RealtimeEvent.CUSTOMER_SERVICE_CONVERSATION_DELETED,
        {"conversation_id": str(conversation_id)},
    )


def conversation_participant_ids(
    *,
    conversation: Conversation,
    admin_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    """会话参与者：用户本人 + 全部启用管理员"""
    return [conversation.user_id, *admin_ids]
