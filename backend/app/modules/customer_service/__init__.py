"""客服模块

负责客服业务数据（会话 / 消息 / 已读），实时传输复用 realtime 模块：
消息、已读、typing、在线状态均通过 realtime 的 Redis Pub/Sub + Socket.IO 推送。
"""
