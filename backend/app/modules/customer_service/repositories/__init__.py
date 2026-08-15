"""客服模块：数据访问"""

from app.modules.customer_service.repositories.conversation import (
    create_conversation,
    get_conversation,
    get_open_conversation_by_user,
    list_all_conversations,
    list_conversations_by_user,
    set_conversation_status,
    touch_conversation,
)
from app.modules.customer_service.repositories.message import (
    create_message,
    list_messages,
    mark_messages_read,
)

__all__ = [
    "create_conversation",
    "get_conversation",
    "get_open_conversation_by_user",
    "list_all_conversations",
    "list_conversations_by_user",
    "set_conversation_status",
    "touch_conversation",
    "create_message",
    "list_messages",
    "mark_messages_read",
]
