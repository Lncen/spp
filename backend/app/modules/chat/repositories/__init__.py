"""聊天模块：数据访问层"""

from app.modules.chat.repositories.chat import (
    advance_last_message,
    create_chat,
    get_chat,
    get_direct_chat,
    list_chats_for_user,
    lock_chat,
)
from app.modules.chat.repositories.message import (
    count_messages,
    create_message,
    get_message,
    get_message_by_client_id,
    list_messages,
)
from app.modules.chat.repositories.participant import (
    add_participant,
    count_unread_by_chat,
    count_unread_for_chat,
    count_unread_total,
    delete_participant,
    get_participant,
    list_participants,
    lock_participant,
    touch_last_read,
)

__all__ = [
    "add_participant",
    "advance_last_message",
    "count_messages",
    "count_unread_by_chat",
    "count_unread_for_chat",
    "count_unread_total",
    "create_chat",
    "create_message",
    "delete_participant",
    "get_chat",
    "get_direct_chat",
    "get_message",
    "get_message_by_client_id",
    "get_participant",
    "list_chats_for_user",
    "list_messages",
    "list_participants",
    "lock_chat",
    "lock_participant",
    "touch_last_read",
]
