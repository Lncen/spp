"""客服模块：数据传输对象"""

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

__all__ = [
    "ConversationCreate",
    "ConversationPublic",
    "ConversationStatusUpdate",
    "ConversationsPublic",
    "MessageCreate",
    "MessagePublic",
    "MessagesPublic",
    "OnlineStatusPublic",
]
