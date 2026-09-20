import { useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { toast } from "sonner"

import { useChat } from "@/components/Chat/ChatProvider"
import {
  CHAT_MESSAGES_QUERY_KEY_PREFIX,
  MY_CHATS_QUERY_KEY,
  MY_CHATS_UNREAD_QUERY_KEY,
} from "@/components/Chat/constants"
import useAuth from "@/hooks/useAuth"
import { useMessageCueVolume } from "@/hooks/useMessageCueVolume"
import { notifyNewMessage, playMessageCue } from "@/lib/new-message-alert"
import { flashTabTitle } from "@/lib/tab-title-flash"
import {
  CHAT_EVENT_MESSAGE_CREATED,
  CHAT_EVENT_MESSAGE_READ,
  CHAT_EVENT_UNREAD_UPDATED,
  PRESENCE_HEARTBEAT_INTERVAL_MS,
  REALTIME_EVENT_PRESENCE_CHANGED,
  REALTIME_EVENT_PRESENCE_HEARTBEAT,
} from "@/realtime/events"
import { useRealtime } from "@/realtime/RealtimeProvider"

type PresenceChangedPayload = {
  user_id: string
  is_online: boolean
}

type UnreadUpdatedPayload = {
  chat_id: string
  unread_count: number
  /** 新消息摘要：只有「收到别人发来的消息」时携带（已读操作不带） */
  message_id?: string
  sender_id?: string | null
  sender_name?: string | null
  message_type?: string
  preview?: string | null
}

/**
 * 实时聊天桥：

 * - `chat.message.created` / `chat.message.read` / `chat.unread.updated` 到达后失效列表与消息缓存，
 *   与通知一致采用「收到事件刷新 + 打开页面兜底拉取」；
 * - 提醒挂在 `chat.unread.updated` 上（定点推给接收人，不依赖是否订阅了该聊天房间）：
 *   任务栏闪烁 + 提示音 + 系统通知（页面不在前台）+ Toast（前台），正在看这条会话时不打扰；
 * - `realtime.presence.changed` 更新在线状态；
 * - 每 30 秒发送 `presence.heartbeat`，服务端在线状态 TTL 为 90 秒。
 */
export function RealtimeChatBridge() {
  const queryClient = useQueryClient()
  const { socket } = useRealtime()
  const { user: currentUser } = useAuth()
  const { activeChatId, openChat, setPresence } = useChat()
  useMessageCueVolume()

  useEffect(() => {
    if (!socket) return

    const invalidateLists = () => {
      queryClient.invalidateQueries({ queryKey: MY_CHATS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: MY_CHATS_UNREAD_QUERY_KEY })
    }

    const handleMessageCreated = () => {
      invalidateLists()
      queryClient.invalidateQueries({
        queryKey: CHAT_MESSAGES_QUERY_KEY_PREFIX,
      })
    }

    const handleMessageRead = () => {
      queryClient.invalidateQueries({ queryKey: MY_CHATS_QUERY_KEY })
      queryClient.invalidateQueries({
        queryKey: ["chat-participants"],
      })
    }

    const handleUnreadUpdated = (payload: UnreadUpdatedPayload) => {
      queryClient.invalidateQueries({ queryKey: MY_CHATS_UNREAD_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: MY_CHATS_QUERY_KEY })
      // 只处理「别人发来新消息」的推送：已读操作不带消息摘要
      if (!payload.message_id || !payload.sender_id) return
      if (payload.sender_id === currentUser?.id) return
      const isOpenChat = payload.chat_id === activeChatId
      if (isOpenChat && document.hasFocus()) return
      const title = payload.sender_name || "新消息"
      const body =
        payload.message_type === "FILE"
          ? payload.preview || "[文件]"
          : payload.preview || ""
      flashTabTitle()
      playMessageCue()
      // 按会话做通知 tag：同一会话的新消息替换旧通知，不同会话依次堆叠
      notifyNewMessage(title, body || undefined, payload.chat_id)
      if (document.hasFocus()) {
        toast(title, {
          description: body || undefined,
          action: {
            label: "查看",
            onClick: () => openChat(payload.chat_id),
          },
        })
      }
    }

    const handlePresenceChanged = (payload: PresenceChangedPayload) => {
      setPresence(payload.user_id, payload.is_online)
    }

    const sendHeartbeat = () => {
      if (socket.connected) {
        socket.emit(REALTIME_EVENT_PRESENCE_HEARTBEAT, {})
      }
    }

    socket.on(CHAT_EVENT_MESSAGE_CREATED, handleMessageCreated)
    socket.on(CHAT_EVENT_MESSAGE_READ, handleMessageRead)
    socket.on(CHAT_EVENT_UNREAD_UPDATED, handleUnreadUpdated)
    socket.on(REALTIME_EVENT_PRESENCE_CHANGED, handlePresenceChanged)
    socket.on("connect", sendHeartbeat)
    sendHeartbeat()
    const heartbeatTimer = window.setInterval(
      sendHeartbeat,
      PRESENCE_HEARTBEAT_INTERVAL_MS,
    )

    return () => {
      window.clearInterval(heartbeatTimer)
      socket.off(CHAT_EVENT_MESSAGE_CREATED, handleMessageCreated)
      socket.off(CHAT_EVENT_MESSAGE_READ, handleMessageRead)
      socket.off(CHAT_EVENT_UNREAD_UPDATED, handleUnreadUpdated)
      socket.off(REALTIME_EVENT_PRESENCE_CHANGED, handlePresenceChanged)
      socket.off("connect", sendHeartbeat)
    }
  }, [
    activeChatId,
    currentUser?.id,
    openChat,
    queryClient,
    setPresence,
    socket,
  ])

  return null
}
