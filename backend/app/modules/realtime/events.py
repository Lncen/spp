"""实时事件名常量

业务模块通过 realtime publisher 发布事件，前端按事件名订阅。
事件名采用与业务事件一致的点分命名，避免与业务 EventBus 事件混淆。
"""


class RealtimeEvent:
    """实时通道事件名"""

    NOTIFICATION_CREATED = "notification.created"
    CUSTOMER_SERVICE_MESSAGE_CREATED = "customer_service.message.created"
    CUSTOMER_SERVICE_MESSAGE_READ = "customer_service.message.read"
    CUSTOMER_SERVICE_CONVERSATION_DELETED = "customer_service.conversation.deleted"
    CUSTOMER_SERVICE_TYPING = "customer_service.typing"
    SYSTEM_CONNECTED = "system.connected"
    SYSTEM_DISCONNECTED = "system.disconnected"
