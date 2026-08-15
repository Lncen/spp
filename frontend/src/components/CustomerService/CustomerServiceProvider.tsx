import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useState,
} from "react"

export const CS_CONVERSATIONS_QUERY_KEY = ["customer-service-conversations"]

export type CustomerServiceView = "chat" | "notifications"

type CustomerServiceContextValue = {
  open: boolean
  /** 当前右侧展示的视图：会话 or 系统通知 */
  view: CustomerServiceView
  /** 需要定位打开的会话（用户表「发起会话」跳转） */
  conversationId: string | null
  openCustomerService: () => void
  openNotifications: () => void
  setView: (view: CustomerServiceView) => void
  openConversation: (conversationId: string) => void
  closeCustomerService: () => void
}

const CustomerServiceContext = createContext<CustomerServiceContextValue>({
  open: false,
  view: "chat",
  conversationId: null,
  openCustomerService: () => {},
  openNotifications: () => {},
  setView: () => {},
  openConversation: () => {},
  closeCustomerService: () => {},
})

export function CustomerServiceProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [view, setView] = useState<CustomerServiceView>("chat")
  const [conversationId, setConversationId] = useState<string | null>(null)

  const openCustomerService = useCallback(() => {
    setView("chat")
    setConversationId(null)
    setOpen(true)
  }, [])

  const openNotifications = useCallback(() => {
    setView("notifications")
    setOpen(true)
  }, [])

  const openConversation = useCallback((id: string) => {
    setView("chat")
    setConversationId(id)
    setOpen(true)
  }, [])

  const closeCustomerService = useCallback(() => {
    setOpen(false)
    setConversationId(null)
    setView("chat")
  }, [])

  return (
    <CustomerServiceContext.Provider
      value={{
        open,
        view,
        conversationId,
        openCustomerService,
        openNotifications,
        setView,
        openConversation,
        closeCustomerService,
      }}
    >
      {children}
    </CustomerServiceContext.Provider>
  )
}

export function useCustomerService() {
  return useContext(CustomerServiceContext)
}
