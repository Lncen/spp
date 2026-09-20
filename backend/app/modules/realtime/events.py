"""实时事件名常量

业务模块通过 realtime publisher 发布事件，前端按事件名订阅。
事件名采用与业务事件一致的点分命名，避免与业务 EventBus 事件混淆。
"""


class RealtimeEvent:
    """实时通道事件名"""

    # 客户端 → 服务端：在线状态心跳
    PRESENCE_HEARTBEAT = "presence.heartbeat"
    # 服务端 → 客户端：某个用户在线状态变化（发给 presence room 订阅者）
    PRESENCE_CHANGED = "realtime.presence.changed"
