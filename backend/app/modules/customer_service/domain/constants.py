"""客服模块：领域常量"""


class ConversationStatus:
    """会话状态"""

    OPEN = "open"
    CLOSED = "closed"


class SenderRole:
    """消息发送方角色"""

    USER = "user"
    ADMIN = "admin"
