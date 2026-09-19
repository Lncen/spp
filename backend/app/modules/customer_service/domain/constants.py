"""客服模块：领域常量"""


class ConversationStatus:
    """会话状态"""

    OPEN = "open"
    CLOSED = "closed"


class SenderRole:
    """消息发送方角色"""

    USER = "user"
    ADMIN = "admin"


# 会话权限码，定义见 app/init_models_data/permissions.py 的「会话」分类
# 用户自助：查看自己的会话（普通用户默认能力）
CONVERSATION_SELF_VIEW_PERMISSION_CODE = "conversation:self_view"
# 客服坐席：查看全部会话 / 操作 / 删除
CONVERSATION_VIEW_PERMISSION_CODE = "conversation:view"
CONVERSATION_REPLY_PERMISSION_CODE = "conversation:reply"
CONVERSATION_UPDATE_PERMISSION_CODE = "conversation:update"
CONVERSATION_DELETE_PERMISSION_CODE = "conversation:delete"
