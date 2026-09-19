import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Send, Trash2 } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"

import {
  type ConversationPublic,
  CustomerServiceService,
  type MessagePublic,
  type MessagesPublic,
} from "@/client"
import { formatDateTime } from "@/components/Admin/Automation/tasks/constants"
import { CS_CONVERSATIONS_QUERY_KEY } from "@/components/CustomerService/CustomerServiceProvider"
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
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Message,
  MessageAvatar,
  MessageContent,
  MessageFooter,
  MessageGroup,
  MessageHeader,
} from "@/components/ui/message"
import useAuth from "@/hooks/useAuth"
import { cn } from "@/lib/utils"
import {
  REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_CREATED,
  REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_READ,
  REALTIME_EVENT_CUSTOMER_SERVICE_TYPING,
} from "@/realtime/events"
import { useRealtime } from "@/realtime/RealtimeProvider"

const CS_MESSAGES_QUERY_KEY = ["customer-service-messages"]
const TYPING_EMIT_INTERVAL_MS = 800
const MESSAGES_PAGE_SIZE = 50
const MESSAGES_LOAD_MORE_THRESHOLD = 120

export function ChatPanel({
  conversationId,
  isAgent,
  canDelete,
  onConversationDeleted,
}: {
  conversationId: string
  isAgent: boolean
  canDelete: boolean
  onConversationDeleted?: () => void
}) {
  const queryClient = useQueryClient()
  const { socket } = useRealtime()
  const { user } = useAuth()
  const currentUserId = user?.id
  const [messages, setMessages] = useState<MessagePublic[]>([])
  const [input, setInput] = useState("")
  const [typingFrom, setTypingFrom] = useState<string | null>(null)
  const typingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastTypingEmitRef = useRef(0)
  const scrollRef = useRef<HTMLDivElement>(null)
  const shouldAutoScrollRef = useRef(true)
  const prevScrollHeightRef = useRef(0)
  const messagesQuery = useQuery({
    queryKey: [...CS_MESSAGES_QUERY_KEY, conversationId],
    queryFn: () =>
      CustomerServiceService.readMessages({
        conversationId,
        limit: MESSAGES_PAGE_SIZE,
      }),
  })

  /** 把新消息合并进消息查询缓存，保证重开/切会话/refetch 不丢实时消息 */
  const mergeMessageIntoCache = useCallback(
    (message: MessagePublic) => {
      queryClient.setQueryData<MessagesPublic>(
        [...CS_MESSAGES_QUERY_KEY, conversationId],
        (current) => {
          if (!current) return current
          if (current.data.some((item) => item.id === message.id)) {
            return current
          }
          return {
            ...current,
            count: current.count + 1,
            data: [message, ...current.data],
          }
        },
      )
    },
    [conversationId, queryClient],
  )

  // 查询数据与本地消息按 id 去重合并，避免整体覆盖导致实时追加的消息丢失
  useEffect(() => {
    if (!messagesQuery.data) return
    setMessages((current) => {
      const seen = new Set(current.map((item) => item.id))
      const fresh = messagesQuery.data.data.filter((item) => !seen.has(item.id))
      return fresh.length ? [...fresh, ...current] : current
    })
  }, [messagesQuery.data])

  const sendMutation = useMutation({
    mutationFn: (content: string) =>
      CustomerServiceService.sendMessageEndpoint({
        conversationId,
        requestBody: { content },
      }),
    onSuccess: (message) => {
      mergeMessageIntoCache(message)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () =>
      CustomerServiceService.deleteConversationEndpoint({ conversationId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CS_CONVERSATIONS_QUERY_KEY })
      onConversationDeleted?.()
    },
  })

  const loadMoreMutation = useMutation({
    mutationFn: (before: string) =>
      CustomerServiceService.readMessages({
        conversationId,
        limit: MESSAGES_PAGE_SIZE,
        before,
      }),
    onSuccess: (page) => {
      const el = scrollRef.current
      prevScrollHeightRef.current = el?.scrollHeight ?? 0
      setMessages((current) => {
        const seen = new Set(current.map((item) => item.id))
        const older = page.data.filter((item) => !seen.has(item.id))
        return older.length ? [...older, ...current] : current
      })
    },
  })

  const markReadMutation = useMutation({
    mutationFn: () =>
      CustomerServiceService.readConversation({ conversationId }),
    onSuccess: () => {
      setMessages((current) =>
        current.map((item) =>
          item.sender_id !== currentUserId && !item.read_at
            ? { ...item, read_at: new Date().toISOString() }
            : item,
        ),
      )
      queryClient.invalidateQueries({ queryKey: CS_CONVERSATIONS_QUERY_KEY })
      queryClient.invalidateQueries({
        queryKey: MY_UNREAD_SUMMARY_QUERY_KEY,
      })
    },
  })

  // 打开会话时，将对方发来的既有消息标记为已读；
  // 会话打开期间到达的新消息保持未读，用于侧边栏角标提示，重新打开会话时再标记已读
  useEffect(() => {
    if (!conversationId) return
    markReadMutation.mutate()
  }, [conversationId, markReadMutation.mutate])

  useEffect(() => {
    if (!socket) return

    const handleMessageCreated = (payload: MessagePublic) => {
      if (payload.conversation_id !== conversationId) return
      mergeMessageIntoCache(payload)
    }
    const handleMessageRead = (payload: {
      conversation_id: string
      reader_role: string
    }) => {
      if (payload.conversation_id !== conversationId) return
      setMessages((current) =>
        current.map((item) =>
          item.sender_id !== currentUserId && !item.read_at
            ? { ...item, read_at: new Date().toISOString() }
            : item,
        ),
      )
    }
    const handleTyping = (payload: {
      conversation_id: string
      user_id: string
    }) => {
      if (payload.conversation_id !== conversationId) return
      if (payload.user_id === currentUserId) return
      setTypingFrom(payload.user_id)
      if (typingTimerRef.current) clearTimeout(typingTimerRef.current)
      typingTimerRef.current = setTimeout(() => setTypingFrom(null), 3000)
    }

    socket.on(
      REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_CREATED,
      handleMessageCreated,
    )
    socket.on(REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_READ, handleMessageRead)
    socket.on(REALTIME_EVENT_CUSTOMER_SERVICE_TYPING, handleTyping)
    return () => {
      socket.off(
        REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_CREATED,
        handleMessageCreated,
      )
      socket.off(
        REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_READ,
        handleMessageRead,
      )
      socket.off(REALTIME_EVENT_CUSTOMER_SERVICE_TYPING, handleTyping)
    }
  }, [socket, conversationId, currentUserId, mergeMessageIntoCache])

  const handleInputChange = (value: string) => {
    setInput(value)
    const now = Date.now()
    if (
      socket &&
      value &&
      now - lastTypingEmitRef.current > TYPING_EMIT_INTERVAL_MS
    ) {
      lastTypingEmitRef.current = now
      socket.emit(REALTIME_EVENT_CUSTOMER_SERVICE_TYPING, {
        conversation_id: conversationId,
      })
    }
  }

  const handleSend = () => {
    const content = input.trim()
    if (!content || sendMutation.isPending) return
    setInput("")
    sendMutation.mutate(content)
  }

  const conversation: ConversationPublic | undefined =
    messagesQuery.data?.conversation
  const hasMore = (messagesQuery.data?.count ?? 0) > messages.length

  // 新消息/输入状态变化时自动滚动到底；用户手动上翻历史时暂停自动滚动
  // biome-ignore lint/correctness/useExhaustiveDependencies: 依赖仅用于触发滚动，effect 内无需读取其值
  useEffect(() => {
    const el = scrollRef.current
    if (el && shouldAutoScrollRef.current) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages, typingFrom])

  const handleMessagesScroll = () => {
    const el = scrollRef.current
    if (!el) return
    shouldAutoScrollRef.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < 100
    const oldest = messages[messages.length - 1]
    if (
      el.scrollTop < MESSAGES_LOAD_MORE_THRESHOLD &&
      hasMore &&
      oldest &&
      !loadMoreMutation.isPending
    ) {
      loadMoreMutation.mutate(oldest.id)
    }
  }

  // 加载更早历史后保持当前视口位置（新增内容插入列表顶部）
  // biome-ignore lint/correctness/useExhaustiveDependencies: 依赖仅用于在 DOM 更新后触发视口补偿
  useEffect(() => {
    const el = scrollRef.current
    if (el && prevScrollHeightRef.current > 0) {
      el.scrollTop += el.scrollHeight - prevScrollHeightRef.current
      prevScrollHeightRef.current = 0
    }
  }, [messages])

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex h-12 shrink-0 items-center justify-between border-b px-4 pr-12">
        <span className="text-sm font-medium">
          {conversation?.user_name ?? "客服会话"}
        </span>
        <div className="flex items-center gap-2">
          {isAgent ? (
            <span
              className={cn(
                "text-xs",
                conversation?.user_online
                  ? "text-emerald-500"
                  : "text-muted-foreground",
              )}
            >
              {conversation?.user_online ? "在线" : "离线"}
            </span>
          ) : null}
          {canDelete ? (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-muted-foreground hover:text-destructive"
                >
                  <Trash2 />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>删除会话</AlertDialogTitle>
                  <AlertDialogDescription>
                    删除后该会话的全部聊天记录将不可恢复，确定删除吗？
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>取消</AlertDialogCancel>
                  <AlertDialogAction
                    disabled={deleteMutation.isPending}
                    onClick={() => deleteMutation.mutate()}
                  >
                    删除
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : null}
        </div>
      </header>

      <div
        ref={scrollRef}
        onScroll={handleMessagesScroll}
        className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-4"
      >
        {loadMoreMutation.isPending ? (
          <div className="py-1 text-center text-xs text-muted-foreground">
            加载更早消息…
          </div>
        ) : null}
        <MessageGroup>
          {messages
            .slice()
            .reverse()
            .map((item) => {
              const isMine = item.sender_id === currentUserId
              return (
                <Message key={item.id} align={isMine ? "end" : "start"}>
                  <MessageAvatar>
                    <Avatar>
                      <AvatarFallback className="text-xs">
                        {isMine
                          ? "我"
                          : (conversation?.user_name ?? "客").slice(0, 1)}
                      </AvatarFallback>
                    </Avatar>
                  </MessageAvatar>
                  <MessageContent>
                    <MessageHeader>
                      <span>
                        {isMine ? "我" : (conversation?.user_name ?? "客服")}
                      </span>
                    </MessageHeader>
                    <Bubble variant={isMine ? "default" : "muted"}>
                      <BubbleContent>{item.content}</BubbleContent>
                    </Bubble>
                    <MessageFooter>
                      <span>{formatDateTime(item.created_at)}</span>
                      {isMine && item.read_at ? <span>已读</span> : null}
                    </MessageFooter>
                  </MessageContent>
                </Message>
              )
            })}
        </MessageGroup>
        {typingFrom ? (
          <div className="text-xs text-muted-foreground">对方正在输入…</div>
        ) : null}
      </div>

      <footer className="flex shrink-0 items-center gap-2 border-t p-3">
        <Input
          value={input}
          placeholder="输入消息…"
          onChange={(event) => handleInputChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.nativeEvent.isComposing) {
              handleSend()
            }
          }}
        />
        <Button size="icon" onClick={handleSend} disabled={!input.trim()}>
          <Send data-icon="inline" />
        </Button>
      </footer>
    </div>
  )
}
