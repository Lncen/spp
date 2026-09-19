"""客服模块：领域常量"""


class ConversationStatus:
    """会话状态"""

    OPEN = "open"
    CLOSED = "closed"


class SenderRole:
    """消息发送方角色"""

    USER = "user"
    ADMIN = "admin"


# 客服坐席权限码：持有即视为接待方，可查看全部会话并以管理端身份回复
# 权限码定义见 app/init_models_data/permissions.py 的「客服管理」分类
AGENT_PERMISSION_CODE = "customer_service:view"
