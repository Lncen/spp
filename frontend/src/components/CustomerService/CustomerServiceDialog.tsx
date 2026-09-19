import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"

import { type ConversationPublic, CustomerServiceService } from "@/client"
import { ChatPanel } from "@/components/CustomerService/ChatPanel"
import {
  CS_CONVERSATIONS_QUERY_KEY,
  useCustomerService,
} from "@/components/CustomerService/CustomerServiceProvider"
import { MY_UNREAD_SUMMARY_QUERY_KEY } from "@/components/Notifications/constants"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
} from "@/components/ui/sidebar"
import usePermissions from "@/hooks/usePermissions"
import { formatRelativeTime } from "@/lib/format-relative-time"
import { cn } from "@/lib/utils"
import {
  REALTIME_EVENT_CUSTOMER_SERVICE_CONVERSATION_DELETED,
  REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_CREATED,
} from "@/realtime/events"
import { useRealtime } from "@/realtime/RealtimeProvider"

function getConversationsQueryOptions() {
  return {
    queryKey: CS_CONVERSATIONS_QUERY_KEY,
    queryFn: () => CustomerServiceService.readConversations({ limit: 100 }),
  }
}

export function CustomerServiceDialog() {
  const queryClient = useQueryClient()
  const { socket } = useRealtime()
  const { open, conversationId, closeCustomerService } = useCustomerService()
  const { hasPermission } = usePermissions()
  // 客服坐席：可查看全部会话；删除会话需单独权限
  const isAgent = hasPermission("customer_service:view")
  const canDeleteConversation = hasPermission("customer_service:delete")
  const [activeId, setActiveId] = useState<string | null>(null)

  const conversationsQuery = useQuery({
    ...getConversationsQueryOptions(),
    enabled: open && isAgent,
  })
  const conversations = conversationsQuery.data?.data ?? []

  // 弹窗级实时监听：无论当前是否选中会话，都刷新会话列表
  useEffect(() => {
    if (!socket || !open) return
    const invalidate = () => {
      queryClient.invalidateQueries({ queryKey: CS_CONVERSATIONS_QUERY_KEY })
      queryClient.invalidateQueries({
        queryKey: MY_UNREAD_SUMMARY_QUERY_KEY,
      })
    }
    const handleDeleted = (payload: { conversation_id: string }) => {
      invalidate()
      queryClient.invalidateQueries({
        queryKey: MY_UNREAD_SUMMARY_QUERY_KEY,
      })
      if (payload.conversation_id === activeId) {
        setActiveId(null)
      }
    }
    socket.on(REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_CREATED, invalidate)
    socket.on(
      REALTIME_EVENT_CUSTOMER_SERVICE_CONVERSATION_DELETED,
      handleDeleted,
    )
    return () => {
      socket.off(REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_CREATED, invalidate)
      socket.off(
        REALTIME_EVENT_CUSTOMER_SERVICE_CONVERSATION_DELETED,
        handleDeleted,
      )
    }
  }, [socket, open, queryClient, activeId])

  // 打开弹窗时：定位到指定会话（用户表「发起会话」）；否则保持当前选择
  useEffect(() => {
    if (!open) return
    if (conversationId) {
      setActiveId(conversationId)
    }
  }, [open, conversationId])

  // 关闭弹窗时清除选中的会话：管理端重新打开时停在会话列表，未读角标不被自动已读清掉
  useEffect(() => {
    if (!open) {
      setActiveId(null)
    }
  }, [open])

  // 普通用户：打开弹窗即获取或创建自己的进行中会话
  useEffect(() => {
    if (!open || isAgent) return
    CustomerServiceService.createConversationEndpoint({}).then(
      (conversation) => {
        setActiveId(conversation.id)
        queryClient.invalidateQueries({
          queryKey: CS_CONVERSATIONS_QUERY_KEY,
        })
      },
    )
  }, [open, isAgent, queryClient])

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => !value && closeCustomerService()}
    >
      <DialogContent className="overflow-hidden p-0 md:h-[650px] md:max-w-[700px] lg:max-w-[780px]">
        <DialogTitle className="sr-only">客服</DialogTitle>
        <DialogDescription className="sr-only">
          客服会话工作台
        </DialogDescription>
        <SidebarProvider className="h-full min-h-0">
          <Sidebar collapsible="none" className="hidden md:flex">
            <SidebarContent className="overflow-y-auto">
              {/* 会话列表：坐席可查看全部会话，普通用户直接进入自己的会话 */}
              {isAgent ? (
                <SidebarGroup>
                  <SidebarGroupContent>
                    <SidebarMenu>
                      {conversations.map((item: ConversationPublic) => (
                        <SidebarMenuItem key={item.id}>
                          <SidebarMenuButton
                            isActive={item.id === activeId}
                            onClick={() => setActiveId(item.id)}
                            className="flex-col items-start gap-1"
                          >
                            <span className="flex w-full items-center justify-between gap-2">
                              <span className="flex min-w-0 items-center gap-1.5">
                                <span className="truncate text-sm font-medium">
                                  {item.user_name ?? item.user_id}
                                </span>
                                {(item.unread_count ?? 0) > 0 ? (
                                  <span className="flex h-4 min-w-4 shrink-0 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium leading-none text-destructive-foreground tabular-nums">
                                    {(item.unread_count ?? 0) > 99
                                      ? "99+"
                                      : item.unread_count}
                                  </span>
                                ) : null}
                              </span>
                              <span className="flex shrink-0 items-center gap-2">
                                <span className="text-xs text-muted-foreground">
                                  {formatRelativeTime(item.last_message_at)}
                                </span>
                                <span
                                  className={cn(
                                    "size-2 shrink-0 rounded-full",
                                    item.user_online
                                      ? "bg-emerald-500"
                                      : "bg-muted-foreground/40",
                                  )}
                                />
                              </span>
                            </span>
                            <span className="w-full truncate text-xs text-muted-foreground">
                              {item.last_message_preview || "暂无消息"}
                            </span>
                          </SidebarMenuButton>
                        </SidebarMenuItem>
                      ))}
                      {conversations.length === 0 ? (
                        <p className="px-3 py-2 text-sm text-muted-foreground">
                          暂无会话
                        </p>
                      ) : null}
                    </SidebarMenu>
                  </SidebarGroupContent>
                </SidebarGroup>
              ) : null}
            </SidebarContent>
          </Sidebar>
          <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
            {activeId ? (
              <ChatPanel
                conversationId={activeId}
                isAgent={isAgent}
                canDelete={canDeleteConversation}
                onConversationDeleted={() => setActiveId(null)}
              />
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
                <p className="text-sm">请选择一个会话</p>
              </div>
            )}
          </main>
        </SidebarProvider>
      </DialogContent>
    </Dialog>
  )
}
