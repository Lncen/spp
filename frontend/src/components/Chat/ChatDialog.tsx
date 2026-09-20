import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query"
import { MessageSquarePlus, Trash2, UserRound, Users } from "lucide-react"
import { useState } from "react"

import { type ChatPublic, ChatService } from "@/client"
import { ChatInfoDialog } from "@/components/Chat/ChatInfoDialog"
import { ChatPanel } from "@/components/Chat/ChatPanel"
import { useChat } from "@/components/Chat/ChatProvider"
import {
  CHAT_LIST_PAGE_SIZE,
  MY_CHATS_QUERY_KEY,
  MY_CHATS_UNREAD_QUERY_KEY,
} from "@/components/Chat/constants"
import { formatChatTime } from "@/components/Chat/format"
import { useTimeRefresh } from "@/components/Chat/useTimeRefresh"
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "@/components/Common/ContextMenu"
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
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

/** 会话列表滚到底部多少像素内就加载下一页 */
const LIST_LOAD_MORE_THRESHOLD = 80

/**
 * 聊天弹窗：左侧「我的聊天」列表，右侧消息面板。
 * 私聊由用户列表的「发起私聊」入口创建，列表里同一对象只会出现一条。
 */
export function ChatDialog() {
  const { open, activeChatId, setActiveChatId, closeChat } = useChat()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()
  const [infoChatId, setInfoChatId] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ChatPublic | null>(null)
  useTimeRefresh()

  const listQuery = useInfiniteQuery({
    queryKey: MY_CHATS_QUERY_KEY,
    queryFn: ({ pageParam }) =>
      ChatService.readMyChats({
        skip: pageParam,
        limit: CHAT_LIST_PAGE_SIZE,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((sum, page) => sum + page.data.length, 0)
      return loaded < lastPage.count ? loaded : undefined
    },
    enabled: open,
  })
  const chats: ChatPublic[] =
    listQuery.data?.pages.flatMap((page) => page.data) ?? []

  /** 会话列表懒加载：滚到底部附近时取下一页 */
  const handleListScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const element = event.currentTarget
    const remaining =
      element.scrollHeight - element.scrollTop - element.clientHeight
    if (
      remaining < LIST_LOAD_MORE_THRESHOLD &&
      listQuery.hasNextPage &&
      !listQuery.isFetchingNextPage
    ) {
      listQuery.fetchNextPage()
    }
  }

  const deleteMutation = useMutation({
    mutationFn: (chatId: string) => ChatService.deleteChat({ chatId }),
    onSuccess: (_message, chatId) => {
      queryClient.invalidateQueries({ queryKey: MY_CHATS_QUERY_KEY })
      queryClient.invalidateQueries({ queryKey: MY_CHATS_UNREAD_QUERY_KEY })
      if (activeChatId === chatId) {
        setActiveChatId(null)
      }
      showSuccessToast("聊天已删除")
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <Dialog open={open} onOpenChange={(value) => !value && closeChat()}>
      <DialogContent className="overflow-hidden p-0 sm:max-w-[900px]">
        <DialogTitle className="sr-only">聊天</DialogTitle>
        <DialogDescription className="sr-only">
          聊天列表与消息
        </DialogDescription>
        <div className="flex h-[640px]">
          <aside className="flex w-64 shrink-0 flex-col border-r">
            <div className="flex flex-col gap-2 border-b p-3">
              <p className="font-medium">我的聊天</p>
            </div>
            <div className="flex-1 overflow-y-auto" onScroll={handleListScroll}>
              {listQuery.isLoading && (
                <div className="flex flex-col gap-2 p-3">
                  <Skeleton className="h-12 w-full" />
                  <Skeleton className="h-12 w-full" />
                </div>
              )}
              {!listQuery.isLoading && chats.length === 0 && (
                <p className="p-4 text-center text-sm text-muted-foreground">
                  还没有聊天，去用户列表发起私聊
                </p>
              )}
              {chats.map((chat) => (
                <ChatListItem
                  key={chat.id}
                  chat={chat}
                  active={chat.id === activeChatId}
                  onSelect={() => setActiveChatId(chat.id)}
                  onQueryInfo={() => setInfoChatId(chat.id)}
                  onDelete={() => setDeleteTarget(chat)}
                />
              ))}
              {listQuery.isFetchingNextPage && (
                <div className="p-3">
                  <Skeleton className="h-12 w-full" />
                </div>
              )}
            </div>
          </aside>
          <section className="flex min-w-0 flex-1 flex-col">
            {activeChatId ? (
              // key 让切换会话时重建面板：滚动位置回到最新消息、状态不会串台
              <ChatPanel key={activeChatId} chatId={activeChatId} />
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
                <MessageSquarePlus className="size-8" />
                选择左侧聊天开始对话
              </div>
            )}
          </section>
        </div>
        {/* 嵌套浮层必须放在 DialogContent 内部：否则 Radix 会把浮层内的点击
            判定为「点在聊天弹窗外部」，从而把整个聊天弹窗关掉 */}
        <ChatInfoDialog
          chatId={infoChatId}
          onOpenChange={(value) => !value && setInfoChatId(null)}
        />
        <AlertDialog
          open={Boolean(deleteTarget)}
          onOpenChange={(value) => !value && setDeleteTarget(null)}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>删除聊天？</AlertDialogTitle>
              <AlertDialogDescription>
                {deleteTarget?.type === "GROUP"
                  ? "你将退出该群聊，群里的其他成员不受影响。"
                  : "聊天会从你的列表移除，对方不受影响；对方再发消息时会重新出现。"}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>取消</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => {
                  if (deleteTarget) {
                    deleteMutation.mutate(deleteTarget.id)
                  }
                  setDeleteTarget(null)
                }}
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

function ChatListItem({
  chat,
  active,
  onSelect,
  onQueryInfo,
  onDelete,
}: {
  chat: ChatPublic
  active: boolean
  onSelect: () => void
  onQueryInfo: () => void
  onDelete: () => void
}) {
  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        <button
          type="button"
          onClick={onSelect}
          className={cn(
            "flex w-full items-center gap-3 border-b px-3 py-2 text-left transition-colors hover:bg-accent",
            active && "bg-accent",
          )}
        >
          <Avatar className="size-9 rounded-[5px]">
            {chat.display_avatar_url && (
              <AvatarImage
                src={chat.display_avatar_url}
                alt={chat.display_name ?? "聊天"}
              />
            )}
            <AvatarFallback className="rounded-[5px] text-xs">
              {chat.type === "GROUP" ? (
                <Users className="size-4" />
              ) : (
                (chat.display_name ?? "聊").slice(0, 1)
              )}
            </AvatarFallback>
          </Avatar>
          <span className="min-w-0 flex-1">
            <span className="flex items-center justify-between gap-2">
              <span className="truncate text-sm font-medium">
                {chat.display_name || chat.name || "聊天"}
              </span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {formatChatTime(chat.last_message_at)}
              </span>
            </span>
            <span className="mt-0.5 flex items-center justify-between gap-2">
              <span className="truncate text-xs text-muted-foreground">
                {chat.last_message_preview || "暂无消息"}
              </span>
              <span className="flex shrink-0 items-center gap-1">
                {Boolean(chat.unread_count) && (
                  <Badge className="shrink-0">{chat.unread_count}</Badge>
                )}
              </span>
            </span>
          </span>
        </button>
      </ContextMenuTrigger>
      <ContextMenuContent className="w-40">
        <ContextMenuItem onSelect={onQueryInfo}>
          <UserRound />
          查询用户信息
        </ContextMenuItem>
        <ContextMenuItem variant="destructive" onSelect={onDelete}>
          <Trash2 />
          删除聊天
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  )
}
