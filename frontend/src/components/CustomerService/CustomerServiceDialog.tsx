import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Info, Trash2, X } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { type ConversationPublic, CustomerServiceService } from "@/client"
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "@/components/Common/ContextMenu"
import { ChatPanel } from "@/components/CustomerService/ChatPanel"
import { ConversationInfoDialog } from "@/components/CustomerService/ConversationInfoDialog"
import {
  CS_CONVERSATIONS_QUERY_KEY,
  useCustomerService,
} from "@/components/CustomerService/CustomerServiceProvider"
import { MY_UNREAD_SUMMARY_QUERY_KEY } from "@/components/Notifications/constants"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
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
import useCustomToast from "@/hooks/useCustomToast"
import usePermissions from "@/hooks/usePermissions"
import { formatRelativeTime } from "@/lib/format-relative-time"
import { cn } from "@/lib/utils"
import {
  REALTIME_EVENT_CUSTOMER_SERVICE_CONVERSATION_DELETED,
  REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_CREATED,
} from "@/realtime/events"
import { useRealtime } from "@/realtime/RealtimeProvider"
import { handleError } from "@/utils"

function getConversationsQueryOptions() {
  return {
    queryKey: CS_CONVERSATIONS_QUERY_KEY,
    queryFn: () => CustomerServiceService.readConversations({ limit: 100 }),
  }
}

function lastMessageTime(conversation: ConversationPublic): number {
  if (!conversation.last_message_at) return 0
  const time = new Date(conversation.last_message_at).getTime()
  return Number.isNaN(time) ? 0 : time
}

export function CustomerServiceDialog() {
  const queryClient = useQueryClient()
  const { socket } = useRealtime()
  const { open, conversationId, closeCustomerService } = useCustomerService()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { hasPermission } = usePermissions()
  // 客服坐席：可查看全部会话；普通用户持有自助查看权限时只看自己的会话
  const isAgent = hasPermission("conversation:view")
  const canViewOwnConversations = hasPermission("conversation:self_view")
  const canListConversations = isAgent || canViewOwnConversations
  const canDeleteConversation = hasPermission("conversation:delete")
  const [activeId, setActiveId] = useState<string | null>(null)
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)
  const [infoConversation, setInfoConversation] =
    useState<ConversationPublic | null>(null)

  const conversationsQuery = useQuery({
    ...getConversationsQueryOptions(),
    enabled: open && canListConversations,
  })
  const conversations = conversationsQuery.data?.data ?? []

  // 排序：有新消息（未读）的会话置顶，其余按最后消息时间倒序
  const sortedConversations = useMemo(
    () =>
      [...conversations].sort((a, b) => {
        const unreadDiff =
          Number((b.unread_count ?? 0) > 0) - Number((a.unread_count ?? 0) > 0)
        if (unreadDiff !== 0) return unreadDiff
        return lastMessageTime(b) - lastMessageTime(a)
      }),
    [conversations],
  )

  const pendingDelete =
    sortedConversations.find((item) => item.id === pendingDeleteId) ?? null

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      CustomerServiceService.deleteConversationEndpoint({ conversationId: id }),
    onSuccess: (_message, id) => {
      setPendingDeleteId(null)
      if (id === activeId) setActiveId(null)
      queryClient.invalidateQueries({ queryKey: CS_CONVERSATIONS_QUERY_KEY })
      queryClient.invalidateQueries({
        queryKey: MY_UNREAD_SUMMARY_QUERY_KEY,
      })
      showSuccessToast("会话已删除")
    },
    onError: handleError.bind(showErrorToast),
  })

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
    if (!open || isAgent || !canViewOwnConversations) return
    CustomerServiceService.createConversationEndpoint({}).then(
      (conversation) => {
        setActiveId(conversation.id)
        queryClient.invalidateQueries({
          queryKey: CS_CONVERSATIONS_QUERY_KEY,
        })
      },
      handleError.bind(showErrorToast),
    )
  }, [open, isAgent, canViewOwnConversations, queryClient])

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => !value && closeCustomerService()}
    >
      {/* grid-rows：标题行按内容高、内容区吃掉剩余高度；否则 auto 行会被
          align-content:stretch 平摊剩余高度（会话为空时表现最明显） */}
      <DialogContent
        showCloseButton={false}
        className="grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden p-0 md:h-[650px] md:max-w-[700px] lg:max-w-[780px]"
      >
        <DialogTitle className="sr-only">客服</DialogTitle>
        <DialogDescription className="sr-only">
          客服会话工作台
        </DialogDescription>
        {/* 关闭按钮独立成行，避免与会话标题、删除等操作挤在同一行 */}
        <div className="flex h-9 shrink-0 items-center justify-end bg-sidebar px-2">
          <DialogClose asChild>
            <Button
              variant="ghost"
              size="icon"
              className="size-8 text-muted-foreground"
            >
              <X />
            </Button>
          </DialogClose>
        </div>
        {/* min-w-0：避免超长用户名把 Dialog 的宽度撑开，导致右侧按钮溢出弹窗 */}
        <SidebarProvider className="h-full min-h-0 min-w-0">
          <Sidebar collapsible="none" className="hidden md:flex">
            <SidebarContent className="overflow-y-auto">
              {/* 会话列表：坐席看全部会话，普通用户看自己的会话（无自助查看权限时不展示） */}
              {canListConversations ? (
                <SidebarGroup>
                  <SidebarGroupContent>
                    <SidebarMenu>
                      {sortedConversations.map((item: ConversationPublic) => (
                        <SidebarMenuItem key={item.id}>
                          <ContextMenu>
                            <ContextMenuTrigger asChild>
                              <SidebarMenuButton
                                isActive={item.id === activeId}
                                onClick={() => setActiveId(item.id)}
                                className="h-auto items-center gap-2 py-2"
                              >
                                <Avatar className="size-10 rounded-[5px]">
                                  <AvatarImage
                                    src={item.user_avatar_url ?? undefined}
                                    alt={item.user_name ?? "用户头像"}
                                  />
                                  <AvatarFallback className="rounded-[5px] text-xs">
                                    {(item.user_name ?? "客").slice(0, 1)}
                                  </AvatarFallback>
                                </Avatar>
                                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                                  <span className="flex w-full items-center justify-between gap-2">
                                    <span className="truncate text-xs font-medium">
                                      {item.user_name ?? item.user_id}
                                    </span>
                                    <span className="flex shrink-0 items-center gap-1.5">
                                      {(item.unread_count ?? 0) > 0 ? (
                                        <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium leading-none text-destructive-foreground tabular-nums">
                                          {(item.unread_count ?? 0) > 99
                                            ? "99+"
                                            : item.unread_count}
                                        </span>
                                      ) : null}
                                      <span className="text-[11px] text-muted-foreground">
                                        {formatRelativeTime(
                                          item.last_message_at,
                                        )}
                                      </span>
                                      {/* 在线状态只对坐席有意义（普通用户视角没有对方在线数据） */}
                                      {isAgent ? (
                                        <span
                                          className={cn(
                                            "size-2 shrink-0 rounded-full",
                                            item.user_online
                                              ? "bg-emerald-500"
                                              : "bg-muted-foreground/40",
                                          )}
                                        />
                                      ) : null}
                                    </span>
                                  </span>
                                  <span className="w-full truncate text-[11px] text-muted-foreground">
                                    {item.last_message_preview || "暂无消息"}
                                  </span>
                                </span>
                              </SidebarMenuButton>
                            </ContextMenuTrigger>
                            <ContextMenuContent className="w-36">
                              <ContextMenuItem
                                onSelect={() => setInfoConversation(item)}
                              >
                                <Info />
                                查看信息
                              </ContextMenuItem>
                              {canDeleteConversation ? (
                                <>
                                  <ContextMenuSeparator />
                                  <ContextMenuItem
                                    variant="destructive"
                                    onSelect={() => setPendingDeleteId(item.id)}
                                  >
                                    <Trash2 />
                                    删除会话
                                  </ContextMenuItem>
                                </>
                              ) : null}
                            </ContextMenuContent>
                          </ContextMenu>
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
              // key：切换会话时重建面板，避免上一个会话的消息、草稿与滚动位置残留串台
              <ChatPanel key={activeId} conversationId={activeId} />
            ) : (
              <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
                <p className="text-sm">
                  {canListConversations ? "请选择一个会话" : "无会话访问权限"}
                </p>
              </div>
            )}
          </main>
        </SidebarProvider>
        <ConversationInfoDialog
          conversation={infoConversation}
          onOpenChange={(value) => !value && setInfoConversation(null)}
        />
        <AlertDialog
          open={Boolean(pendingDelete)}
          onOpenChange={(value) => !value && setPendingDeleteId(null)}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>删除会话</AlertDialogTitle>
              <AlertDialogDescription>
                删除「{pendingDelete?.user_name ?? pendingDelete?.user_id}
                」后该会话的全部聊天记录将不可恢复，确定删除吗？
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>取消</AlertDialogCancel>
              <AlertDialogAction
                disabled={deleteMutation.isPending}
                onClick={() =>
                  pendingDelete && deleteMutation.mutate(pendingDelete.id)
                }
              >
                删除
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </DialogContent>
    </Dialog>
  )
}
