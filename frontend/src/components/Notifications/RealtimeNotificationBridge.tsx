import { useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { toast } from "sonner"

import {
  MY_NOTIFICATIONS_QUERY_KEY,
  MY_NOTIFICATIONS_UNREAD_QUERY_KEY,
  MY_UNREAD_SUMMARY_QUERY_KEY,
} from "@/components/Notifications/constants"
import { useMessageCueVolume } from "@/hooks/useMessageCueVolume"
import { notifyNewMessage, playMessageCue } from "@/lib/new-message-alert"
import { flashTabTitle } from "@/lib/tab-title-flash"
import { REALTIME_EVENT_NOTIFICATION_CREATED } from "@/realtime/events"
import { useRealtime } from "@/realtime/RealtimeProvider"

type NotificationCreatedPayload = {
  id: string
  title: string
  content: string
  event_type: string
  payload_snapshot: Record<string, unknown>
  created_at: string | null
  read_at: string | null
}

/**
 * 实时通知桥：收到 notification.created 后刷新未读数与列表，并弹出 Toast。
 * 实时通道只是提醒，PostgreSQL 才是事实来源；打开通知中心时仍会兜底拉取。
 */
export function RealtimeNotificationBridge() {
  const queryClient = useQueryClient()
  const { socket } = useRealtime()
  useMessageCueVolume()

  useEffect(() => {
    if (!socket) return

    const handleCreated = (payload: NotificationCreatedPayload) => {
      // 页面不在前台时闪烁任务栏标签
      flashTabTitle()
      notifyNewMessage(payload.title, payload.content || undefined)
      playMessageCue()
      queryClient.invalidateQueries({
        queryKey: MY_NOTIFICATIONS_UNREAD_QUERY_KEY,
      })
      queryClient.invalidateQueries({
        queryKey: MY_NOTIFICATIONS_QUERY_KEY,
      })
      queryClient.invalidateQueries({
        queryKey: MY_UNREAD_SUMMARY_QUERY_KEY,
      })
      if (document.hasFocus()) {
        toast(payload.title, {
          description: payload.content || undefined,
        })
      }
    }

    socket.on(REALTIME_EVENT_NOTIFICATION_CREATED, handleCreated)
    return () => {
      socket.off(REALTIME_EVENT_NOTIFICATION_CREATED, handleCreated)
    }
  }, [queryClient, socket])

  return null
}
