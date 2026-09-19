import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Send } from "lucide-react"
import { Fragment, useCallback, useEffect, useRef, useState } from "react"

import {
  type ConversationPublic,
  CustomerServiceService,
  type MessagePublic,
  type MessagesPublic,
} from "@/client"
import { CS_CONVERSATIONS_QUERY_KEY } from "@/components/CustomerService/CustomerServiceProvider"
import { MY_UNREAD_SUMMARY_QUERY_KEY } from "@/components/Notifications/constants"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Message,
  MessageAvatar,
  MessageContent,
  MessageGroup,
} from "@/components/ui/message"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import usePermissions from "@/hooks/usePermissions"
import {
  REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_CREATED,
  REALTIME_EVENT_CUSTOMER_SERVICE_MESSAGE_READ,
  REALTIME_EVENT_CUSTOMER_SERVICE_TYPING,
} from "@/realtime/events"
import { useRealtime } from "@/realtime/RealtimeProvider"
import { handleError } from "@/utils"

const CS_MESSAGES_QUERY_KEY = ["customer-service-messages"]
const TYPING_EMIT_INTERVAL_MS = 800
const MESSAGES_PAGE_SIZE = 50
const MESSAGES_LOAD_MORE_THRESHOLD = 120
/** 相邻消息间隔超过该时长时插入居中的时间分隔 */
const TIME_DIVIDER_GAP_MS = 5 * 60 * 1000

/** 时间分隔文案：当天只显示 HH:mm，跨天补上日期 */
function formatMessageTime(value?: string | null): string {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  const time = date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  })
  if (date.toDateString() === new Date().toDateString()) return time
  return `${date.getMonth() + 1}月${date.getDate()}日 ${time}`
}

/** 首条消息、跨天或与上一条间隔超过 5 分钟时显示时间分隔 */
function shouldShowTimeDivider(
  messages: MessagePublic[],
  index: number,
): boolean {
  const current = messages[index]
  if (!current?.created_at) return index === 0
  if (index === 0) return true
  const previous = messages[index - 1]
  const currentAt = new Date(current.created_at).getTime()
  const previousAt = previous?.created_at
    ? new Date(previous.created_at).getTime()
    : Number.NaN
  if (Number.isNaN(currentAt) || Number.isNaN(previousAt)) return true
  return currentAt - previousAt >= TIME_DIVIDER_GAP_MS
}

export function ChatPanel({
  conversationId,
}: {
  conversationId: string
}) {
  const queryClient = useQueryClient()
  const { socket } = useRealtime()
  const { user } = useAuth()
  const { hasPermission } = usePermissions()
  const { showErrorToast } = useCustomToast()
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
    onError: handleError.bind(showErrorToast),
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
    onError: handleError.bind(showErrorToast),
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
    onError: handleError.bind(showErrorToast),
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
  // 会话数据未加载完成前不限制输入，避免闪烁；
  // 加载后按规则控制：会话参与者（本人或坐席）持有「回复会话」权限才能发送
  const isConversationOpen = conversation?.status === "open"
  const canSend =
    conversation === undefined
      ? true
      : isConversationOpen && hasPermission("conversation:reply")
  const sendPlaceholder = !conversation
    ? "输入消息…"
    : !isConversationOpen
      ? "会话已关闭"
      : canSend
        ? "输入消息…"
        : "无权发送消息"
  const hasMore = (messagesQuery.data?.count ?? 0) > messages.length
  // 接口按最新在前返回，本地也按此顺序合并，渲染前翻转为时间正序
  const chronologicalMessages = messages.slice().reverse()

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
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <header className="flex h-12 min-w-0 shrink-0 items-center justify-between gap-3 border-b px-4">
        <span
          className="min-w-0 flex-1 truncate text-xs font-medium"
          title={conversation?.user_name ?? undefined}
        >
          {conversation?.user_name ?? "客服会话"}
        </span>
      </header>

      <div
        ref={scrollRef}
        onScroll={handleMessagesScroll}
        className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-4"
      >
        {loadMoreMutation.isPending ? (
          <div className="py-1 text-center text-[11px] text-muted-foreground">
            加载更早消息…
          </div>
        ) : null}
        <MessageGroup>
          {chronologicalMessages.map((item, index) => {
            const isMine = item.sender_id === currentUserId
            return (
              <Fragment key={item.id}>
                {shouldShowTimeDivider(chronologicalMessages, index) ? (
                  <div className="py-1 text-center text-[11px] text-muted-foreground">
                    {formatMessageTime(item.created_at)}
                  </div>
                ) : null}
                <Message align={isMine ? "end" : "start"}>
                  <MessageAvatar className="self-start rounded-[5px]">
                    <Avatar className="size-8 rounded-[5px]">
                      {!isMine && conversation?.user_avatar_url ? (
                        <AvatarImage
                          src={conversation.user_avatar_url}
                          alt={conversation.user_name ?? "用户头像"}
                        />
                      ) : null}
                      <AvatarFallback className="rounded-[5px] text-xs font-medium">
                        {isMine
                          ? "我"
                          : (conversation?.user_name ?? "客").slice(0, 1)}
                      </AvatarFallback>
                    </Avatar>
                  </MessageAvatar>
                  <MessageContent>
                    <Bubble variant={isMine ? "default" : "muted"}>
                      {/* 行高 20px + 上下各 5px + 边框 = 32px，与 size-8 头像等高 */}
                      <BubbleContent className="rounded-[5px] px-3 py-[5px] text-xs leading-5">
                        {item.content}
                      </BubbleContent>
                    </Bubble>
                  </MessageContent>
                </Message>
              </Fragment>
            )
          })}
        </MessageGroup>
        {typingFrom ? (
          <div className="text-[11px] text-muted-foreground">对方正在输入…</div>
        ) : null}
      </div>

      <footer className="flex shrink-0 items-center gap-2 border-t p-3">
        <Input
          className="text-xs"
          value={input}
          placeholder={sendPlaceholder}
          disabled={!canSend}
          onChange={(event) => handleInputChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.nativeEvent.isComposing) {
              handleSend()
            }
          }}
        />
        <Button
          size="icon"
          onClick={handleSend}
          disabled={!canSend || !input.trim()}
        >
          <Send data-icon="inline" />
        </Button>
      </footer>
    </div>
  )
}
