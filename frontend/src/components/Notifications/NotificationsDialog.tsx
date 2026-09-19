import { NotificationPanel } from "@/components/Notifications/NotificationPanel"
import { useNotifications } from "@/components/Notifications/NotificationsProvider"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"

/**
 * 系统通知弹窗：由侧边栏「通知」入口打开，与客服会话工作台相互独立。
 */
export function NotificationsDialog() {
  const { open, closeNotifications } = useNotifications()

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => !value && closeNotifications()}
    >
      <DialogContent className="overflow-hidden p-0 sm:max-w-[640px] md:h-[650px]">
        <DialogTitle className="sr-only">系统通知</DialogTitle>
        <DialogDescription className="sr-only">系统通知列表</DialogDescription>
        <NotificationPanel active={open} />
      </DialogContent>
    </Dialog>
  )
}
