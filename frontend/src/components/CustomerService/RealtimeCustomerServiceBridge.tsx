import { useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { toast } from "sonner"

import type { ConversationsPublic, MessagePublic } from "@/client"
import { CS_CONVERSATIONS_QUERY_KEY } from "@/components/CustomerService/CustomerServiceProvider"
import { MY_UNREAD_SUMMARY_QUERY_KEY } from "@/components/Notifications/constants"
import useAuth from "@/hooks/useAuth"
import { useMessageCueVolume } from "@/hooks/useMessageCueVolume"
import { notifyNewMessage, playMessageCue } from "@/lib/new-message-alert"
import { flashTabTitle } from "@/lib/tab-title-flash"
import { REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_CREATED } from "@/realtime/events"
import { useRealtime } from "@/realtime/RealtimeProvider"

/**
 * 实时客服消息桥：在主页/任意页面收到他人发来的客服消息时，
 * 刷新会话列表（未读数、最后消息）并弹出 Toast 提醒。
 * 实时通道只是提醒，PostgreSQL 才是事实来源。
 */
export function RealtimeCustomerServiceBridge() {
  const queryClient = useQueryClient()
  const { socket } = useRealtime()
  const { user } = useAuth()
  const currentUserId = user?.id
  useMessageCueVolume()

  useEffect(() => {
    if (!socket) return

    const handleCreated = (payload: MessagePublic) => {
      // 自己发的消息不提醒
      if (payload.sender_id === currentUserId) return
      queryClient.invalidateQueries({
        queryKey: CS_CONVERSATIONS_QUERY_KEY,
      })
      queryClient.invalidateQueries({
        queryKey: MY_UNREAD_SUMMARY_QUERY_KEY,
      })
      const conversations =
        queryClient.getQueryData<ConversationsPublic>(
          CS_CONVERSATIONS_QUERY_KEY,
        )?.data ?? []
      const conversation = conversations.find(
        (item) => item.id === payload.conversation_id,
      )
      const name =
        conversation?.user_name ??
        (payload.sender_role === "admin" ? "客服" : "用户")
      // 页面不在前台时闪烁任务栏标签 + 系统通知 + 提示音
      flashTabTitle()
      notifyNewMessage(name, payload.content)
      playMessageCue()
      toast(name, {
        description: payload.content,
      })
    }

    socket.on(REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_CREATED, handleCreated)
    return () => {
      socket.off(REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_CREATED, handleCreated)
    }
  }, [socket, queryClient, currentUserId])

  return null
}
