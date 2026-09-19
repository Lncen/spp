import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useState,
} from "react"

export const CS_CONVERSATIONS_QUERY_KEY = ["customer-service-conversations"]

type CustomerServiceContextValue = {
  /** 客服会话弹窗是否打开 */
  open: boolean
  /** 需要定位打开的会话（用户表「发起会话」跳转） */
  conversationId: string | null
  openCustomerService: () => void
  openConversation: (conversationId: string) => void
  closeCustomerService: () => void
}

const CustomerServiceContext = createContext<CustomerServiceContextValue>({
  open: false,
  conversationId: null,
  openCustomerService: () => {},
  openConversation: () => {},
  closeCustomerService: () => {},
})

export function CustomerServiceProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)

  const openCustomerService = useCallback(() => {
    setConversationId(null)
    setOpen(true)
  }, [])

  const openConversation = useCallback((id: string) => {
    setConversationId(id)
    setOpen(true)
  }, [])

  const closeCustomerService = useCallback(() => {
    setOpen(false)
    setConversationId(null)
  }, [])

  return (
    <CustomerServiceContext.Provider
      value={{
        open,
        conversationId,
        openCustomerService,
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
