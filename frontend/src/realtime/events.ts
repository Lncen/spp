export const REALTIME_EVENT_NOTIFICATION_CREATED = "notification.created"

/** 客户端 → 服务端：在线状态心跳（服务端在线状态 TTL 为 90 秒） */
export const REALTIME_EVENT_PRESENCE_HEARTBEAT = "presence.heartbeat"
/** 服务端 → 客户端：某个用户在线状态变化 */
export const REALTIME_EVENT_PRESENCE_CHANGED = "realtime.presence.changed"

/** 心跳间隔：与服务端 PRESENCE_HEARTBEAT_SECONDS 保持一致 */
export const PRESENCE_HEARTBEAT_INTERVAL_MS = 30_000

/** 客户端 → 服务端：聊天事件 */
export const CHAT_EVENT_SUBSCRIBE = "chat.subscribe"
export const CHAT_EVENT_UNSUBSCRIBE = "chat.unsubscribe"
export const CHAT_EVENT_MESSAGE_SEND = "chat.message.send"
export const CHAT_EVENT_TYPING = "chat.typing"
export const CHAT_EVENT_READ = "chat.read"

/** 服务端 → 客户端：聊天事件 */
export const CHAT_EVENT_MESSAGE_CREATED = "chat.message.created"
export const CHAT_EVENT_MESSAGE_READ = "chat.message.read"
export const CHAT_EVENT_UNREAD_UPDATED = "chat.unread.updated"
