/** 我参与的聊天列表 */
export const MY_CHATS_QUERY_KEY = ["my-chats"] as const

/** 聊天未读总数（侧边栏角标） */
export const MY_CHATS_UNREAD_QUERY_KEY = ["my-chats-unread"] as const

/** 消息分页缓存的公共前缀（事件到达时按前缀失效） */
export const CHAT_MESSAGES_QUERY_KEY_PREFIX = ["chat-messages"] as const

/** 单个聊天的消息分页缓存 */
export const chatMessagesQueryKey = (chatId: string) =>
  [...CHAT_MESSAGES_QUERY_KEY_PREFIX, chatId] as const

/** 单个聊天的成员缓存（含在线状态与已读游标） */
export const chatParticipantsQueryKey = (chatId: string) =>
  ["chat-participants", chatId] as const

/** 消息分页每页条数（与服务端默认值一致） */
export const CHAT_MESSAGE_PAGE_SIZE = 50

/** typing 状态的本地展示时长（毫秒） */
export const TYPING_VISIBLE_MS = 5_000
