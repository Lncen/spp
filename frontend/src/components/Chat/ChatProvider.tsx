import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useState,
} from "react"

type ChatContextValue = {
  /** 聊天弹窗是否打开 */
  open: boolean
  /** 当前打开的聊天 ID（null 表示只看列表） */
  activeChatId: string | null
  /** 用户在线状态（由 realtime.presence.changed 实时更新） */
  presence: Record<string, boolean>
  openChat: (chatId?: string | null) => void
  setActiveChatId: (chatId: string | null) => void
  closeChat: () => void
  setPresence: (userId: string, isOnline: boolean) => void
}

const ChatContext = createContext<ChatContextValue>({
  open: false,
  activeChatId: null,
  presence: {},
  openChat: () => {},
  setActiveChatId: () => {},
  closeChat: () => {},
  setPresence: () => {},
})

/**
 * 聊天弹窗状态：侧边栏「聊天」入口与用户操作菜单「发起私聊」都通过它打开会话。
 * 在线状态集中在这里，供聊天面板与成员列表共用。
 */
export function ChatProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [activeChatId, setActiveChatId] = useState<string | null>(null)
  const [presence, setPresenceMap] = useState<Record<string, boolean>>({})

  const openChat = useCallback((chatId?: string | null) => {
    setOpen(true)
    if (chatId !== undefined) {
      setActiveChatId(chatId)
    }
  }, [])

  const closeChat = useCallback(() => setOpen(false), [])

  const setPresence = useCallback((userId: string, isOnline: boolean) => {
    setPresenceMap((current) =>
      current[userId] === isOnline
        ? current
        : { ...current, [userId]: isOnline },
    )
  }, [])

  return (
    <ChatContext.Provider
      value={{
        open,
        activeChatId,
        presence,
        openChat,
        setActiveChatId,
        closeChat,
        setPresence,
      }}
    >
      {children}
    </ChatContext.Provider>
  )
}

export function useChat() {
  return useContext(ChatContext)
}
