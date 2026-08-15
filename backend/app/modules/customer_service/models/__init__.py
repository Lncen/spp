"""客服模块：数据模型"""

from app.modules.customer_service.models.conversation import Conversation
from app.modules.customer_service.models.message import ConversationMessage

__all__ = ["Conversation", "ConversationMessage"]
