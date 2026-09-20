import { useInfiniteQuery, useQuery } from "@tanstack/react-query"
import { ArrowUp } from "lucide-react"
import { Fragment, useEffect, useMemo, useRef, useState } from "react"

import {
  ChatService,
  type MessagePublic,
  type ParticipantPublic,
} from "@/client"
import { useChat } from "@/components/Chat/ChatProvider"
import {
  CHAT_MESSAGE_PAGE_SIZE,
  chatMessagesQueryKey,
  chatParticipantsQueryKey,
  TYPING_VISIBLE_MS,
} from "@/components/Chat/constants"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Button } from "@/components/ui/button"
import { Message, MessageAvatar, MessageContent } from "@/components/ui/message"
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller"
import { Textarea } from "@/components/ui/textarea"
import useAuth from "@/hooks/useAuth"
import { cn } from "@/lib/utils"
import {
  CHAT_EVENT_MESSAGE_SEND,
  CHAT_EVENT_READ,
  CHAT_EVENT_SUBSCRIBE,
  CHAT_EVENT_TYPING,
  CHAT_EVENT_UNSUBSCRIBE,
} from "@/realtime/events"
import { useRealtime } from "@/realtime/RealtimeProvider"
import { formatChatTime } from "./format"
import { useTimeRefresh } from "./useTimeRefresh"

type TypingPayload = {
  chat_id: string
  user_id: string
  is_typing: boolean
}

/** 相邻消息超过该间隔就插入一次居中时间分隔 */
const TIME_DIVIDER_GAP_MS = 5 * 60 * 1000

/**
 * 聊天面板：订阅聊天房间、加载历史消息、发送与已读。

 * - 消息列表按 `(created_at, id)` 倒序返回，这里反序渲染成时间正序；
 * - 发送走 Socket.IO（`chat.message.send`），服务端先落库再广播；
 * - 打开聊天即订阅房间并标记已读，关闭时取消订阅与 presence 订阅。
 */
export function ChatPanel({ chatId }: { chatId: string }) {
  const { socket } = useRealtime()
  const { user: currentUser } = useAuth()
  const { presence } = useChat()
  useTimeRefresh()
  const [draft, setDraft] = useState("")
  const [typingUsers, setTypingUsers] = useState<Record<string, number>>({})
  const typingResetTimer = useRef<number | null>(null)
  const lastReadMessageId = useRef<string | null>(null)

  const participantsQuery = useQuery({
    queryKey: chatParticipantsQueryKey(chatId),
    queryFn: () => ChatService.readChatParticipants({ chatId }),
  })
  const messagesQuery = useInfiniteQuery({
    queryKey: chatMessagesQueryKey(chatId),
    queryFn: ({ pageParam }) =>
      ChatService.readChatMessages({
        chatId,
        limit: CHAT_MESSAGE_PAGE_SIZE,
        before: pageParam ?? undefined,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((sum, page) => sum + page.data.length, 0)
      if (loaded >= lastPage.count) return undefined
      return lastPage.data[lastPage.data.length - 1]?.id
    },
  })

  /** 消息按时间正序展示（服务端返回最新在前） */
  const messages = useMemo(() => {
    const pages = messagesQuery.data?.pages ?? []
    return pages
      .flatMap((page) => page.data)
      .slice()
      .reverse()
  }, [messagesQuery.data])

  const newestMessage = messagesQuery.data?.pages[0]?.data[0]
  const counterpart = useMemo(
    () =>
      participantsQuery.data?.data.find(
        (item) => item.user_id !== currentUser?.id,
      ),
    [currentUser?.id, participantsQuery.data],
  )
  /** 成员索引：消息行按发送者取头像与展示名 */
  const participantById = useMemo(() => {
    const map = new Map<string, ParticipantPublic>()
    for (const item of participantsQuery.data?.data ?? []) {
      map.set(item.user_id, item)
    }
    return map
  }, [participantsQuery.data])
  const counterpartOnline = counterpart
    ? (presence[counterpart.user_id] ?? counterpart.is_online ?? false)
    : false

  // 订阅聊天房间：进入即订阅，离开即取消订阅（含 presence 房间）
  useEffect(() => {
    if (!socket || !chatId) return
    socket.emit(CHAT_EVENT_SUBSCRIBE, { chat_id: chatId })
    return () => {
      socket.emit(CHAT_EVENT_UNSUBSCRIBE, { chat_id: chatId })
    }
  }, [chatId, socket])

  // typing：只展示其他参与者的输入状态，超时自动清除
  useEffect(() => {
    if (!socket) return
    const handleTyping = (payload: TypingPayload) => {
      if (payload.chat_id !== chatId || payload.user_id === currentUser?.id) {
        return
      }
      setTypingUsers((current) => {
        const next = { ...current }
        if (payload.is_typing) {
          next[payload.user_id] = Date.now() + TYPING_VISIBLE_MS
        } else {
          delete next[payload.user_id]
        }
        return next
      })
    }
    socket.on(CHAT_EVENT_TYPING, handleTyping)
    return () => {
      socket.off(CHAT_EVENT_TYPING, handleTyping)
    }
  }, [chatId, currentUser?.id, socket])

  useEffect(() => {
    const timer = window.setInterval(() => {
      setTypingUsers((current) => {
        const expired = Object.entries(current).filter(
          ([, expiresAt]) => expiresAt <= Date.now(),
        )
        if (expired.length === 0) return current
        const next = { ...current }
        for (const [userId] of expired) {
          delete next[userId]
        }
        return next
      })
    }, 1_000)
    return () => window.clearInterval(timer)
  }, [])

  // 打开聊天 / 收到新消息后标记已读（游标只前进，重复提交无副作用）
  useEffect(() => {
    if (!socket || !newestMessage) return
    if (newestMessage.sender_id === currentUser?.id) return
    // 只在最新消息变化时上报一次，避免缓存刷新触发重复请求
    if (lastReadMessageId.current === newestMessage.id) return
    lastReadMessageId.current = newestMessage.id
    socket.emit(CHAT_EVENT_READ, {
      chat_id: chatId,
      message_id: newestMessage.id,
    })
  }, [chatId, currentUser?.id, newestMessage, socket])

  const handleDraftChange = (value: string) => {
    setDraft(value)
    if (!socket || !value.trim()) return
    socket.emit(CHAT_EVENT_TYPING, { chat_id: chatId, is_typing: true })
    if (typingResetTimer.current !== null) {
      window.clearTimeout(typingResetTimer.current)
    }
    typingResetTimer.current = window.setTimeout(() => {
      socket.emit(CHAT_EVENT_TYPING, { chat_id: chatId, is_typing: false })
      typingResetTimer.current = null
    }, 3_000)
  }

  const handleSend = () => {
    const content = draft.trim()
    if (!socket?.connected || !content) return
    socket.emit(CHAT_EVENT_MESSAGE_SEND, {
      chat_id: chatId,
      content,
      message_type: "TEXT",
      client_message_id: crypto.randomUUID(),
    })
    setDraft("")
    socket.emit(CHAT_EVENT_TYPING, { chat_id: chatId, is_typing: false })
  }

  const typingNames = Object.keys(typingUsers)
    .map(
      (userId) =>
        participantsQuery.data?.data.find((item) => item.user_id === userId)
          ?.display_name ?? "对方",
    )
    .join("、")

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b px-4">
        <div className="min-w-0">
          <p className="truncate font-medium">
            {participantsQuery.data?.data.length
              ? counterpart?.display_name || "聊天"
              : "聊天"}
          </p>
          <p className="text-xs text-muted-foreground">
            {typingNames
              ? `${typingNames} 正在输入…`
              : counterpartOnline
                ? "在线"
                : "离线"}
          </p>
        </div>
      </header>

      <MessageScrollerProvider autoScroll>
        <MessageScroller>
          <MessageScrollerViewport>
            <MessageScrollerContent className="gap-4 p-4">
              {messagesQuery.hasNextPage && (
                <MessageScrollerItem>
                  <div className="flex justify-center">
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={messagesQuery.isFetchingNextPage}
                      onClick={() => messagesQuery.fetchNextPage()}
                    >
                      {messagesQuery.isFetchingNextPage
                        ? "加载中…"
                        : "加载更早消息"}
                    </Button>
                  </div>
                </MessageScrollerItem>
              )}
              {messages.map((message, index) => {
                const isMine = message.sender_id === currentUser?.id
                const sender = message.sender_id
                  ? participantById.get(message.sender_id)
                  : undefined
                const senderName = isMine
                  ? "我"
                  : (message.sender_name ?? sender?.display_name ?? "对方")
                return (
                  <Fragment key={message.id}>
                    {showTimeDivider(messages, index) && (
                      <MessageScrollerItem>
                        <TimeDivider value={message.created_at} />
                      </MessageScrollerItem>
                    )}
                    <MessageScrollerItem messageId={message.id}>
                      <Message align={isMine ? "end" : "start"}>
                        {/* 外层容器自身是 rounded-full + overflow-hidden，必须一起改成方形，
                            否则会把里面的方形头像裁成圆形 */}
                        <MessageAvatar className="rounded-[5px]">
                          <Avatar className="size-9 rounded-[5px]">
                            {sender?.display_avatar_url && (
                              <AvatarImage
                                src={sender.display_avatar_url}
                                alt={senderName}
                              />
                            )}
                            <AvatarFallback className="rounded-[5px] text-xs">
                              {senderName.slice(0, 1)}
                            </AvatarFallback>
                          </Avatar>
                        </MessageAvatar>
                        <MessageContent>
                          <Bubble
                            variant={isMine ? "default" : "muted"}
                            align={isMine ? "end" : "start"}
                          >
                            {/* 单行气泡高度与头像对齐（36px）：行高 20px + 上下内边距 16px */}
                            <BubbleContent className="min-h-9 rounded-[5px] px-3 py-2 text-[13px] leading-5">
                              {message.message_type === "FILE"
                                ? message.file_name || "[文件]"
                                : message.content}
                            </BubbleContent>
                            {/* 气泡小尾巴：用同色小方块旋转 45° 贴在外侧边缘 */}
                            <span
                              aria-hidden
                              className={cn(
                                "absolute top-2 size-2 rotate-45 rounded-[1px]",
                                isMine
                                  ? "right-[-3px] bg-primary"
                                  : "left-[-3px] bg-muted",
                              )}
                            />
                          </Bubble>
                        </MessageContent>
                      </Message>
                    </MessageScrollerItem>
                  </Fragment>
                )
              })}
              {!messagesQuery.isLoading && messages.length === 0 && (
                <MessageScrollerItem>
                  <p className="py-10 text-center text-sm text-muted-foreground">
                    还没有消息，发送第一条消息开始聊天
                  </p>
                </MessageScrollerItem>
              )}
            </MessageScrollerContent>
          </MessageScrollerViewport>
          <MessageScrollerButton />
        </MessageScroller>
      </MessageScrollerProvider>

      <footer className="shrink-0 border-t p-3">
        <div className="flex items-end gap-2">
          <Textarea
            value={draft}
            rows={2}
            maxLength={2000}
            placeholder={
              socket?.connected ? "输入消息，Enter 发送" : "实时通道未连接"
            }
            className="max-h-32 min-h-10 resize-none"
            onChange={(event) => handleDraftChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault()
                handleSend()
              }
            }}
          />
          <Button
            size="icon"
            disabled={!socket?.connected || !draft.trim()}
            onClick={handleSend}
          >
            <ArrowUp />
            <span className="sr-only">发送</span>
          </Button>
        </div>
      </footer>
    </div>
  )
}

/** 居中时间分隔（与微信类似：首条以及与上一条间隔超过 5 分钟时展示） */
function TimeDivider({ value }: { value?: string | null }) {
  return (
    <div className="flex justify-center py-1">
      <span className="text-xs text-muted-foreground">
        {formatChatTime(value)}
      </span>
    </div>
  )
}

function showTimeDivider(messages: MessagePublic[], index: number): boolean {
  const current = messages[index]
  if (!current?.created_at) return false
  if (index === 0) return true
  const previous = messages[index - 1]
  if (!previous?.created_at) return true
  const currentAt = new Date(current.created_at).getTime()
  const previousAt = new Date(previous.created_at).getTime()
  if (Number.isNaN(currentAt) || Number.isNaN(previousAt)) return false
  // 跨天必出，同一分钟内也必出（相当于会话开始的分隔）
  if (
    new Date(currentAt).toDateString() !== new Date(previousAt).toDateString()
  ) {
    return true
  }
  return currentAt - previousAt >= TIME_DIVIDER_GAP_MS
}
