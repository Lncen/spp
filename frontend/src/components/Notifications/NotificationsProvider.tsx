import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useState,
} from "react"

type NotificationsContextValue = {
  /** 系统通知弹窗是否打开 */
  open: boolean
  openNotifications: () => void
  closeNotifications: () => void
}

const NotificationsContext = createContext<NotificationsContextValue>({
  open: false,
  openNotifications: () => {},
  closeNotifications: () => {},
})

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)

  const openNotifications = useCallback(() => setOpen(true), [])
  const closeNotifications = useCallback(() => setOpen(false), [])

  return (
    <NotificationsContext.Provider
      value={{ open, openNotifications, closeNotifications }}
    >
      {children}
    </NotificationsContext.Provider>
  )
}

export function useNotifications() {
  return useContext(NotificationsContext)
}
