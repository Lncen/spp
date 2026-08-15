import type { UserListItemPublic } from "@/client"
import { SendNotificationForm } from "@/components/Admin/Notifications/SendNotificationForm"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

interface SendUserNotificationDialogProps {
  user: UserListItemPublic
  open: boolean
  onOpenChange: (open: boolean) => void
  /** 发送成功后关闭外层下拉菜单 */
  onSuccess: () => void
}

export const SendUserNotificationDialog = ({
  user,
  open,
  onOpenChange,
  onSuccess,
}: SendUserNotificationDialogProps) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>发送通知：{user.username}</DialogTitle>
          <DialogDescription>
            向该用户发送通知并异步投递，可同时选择站内与邮件渠道
          </DialogDescription>
        </DialogHeader>
        <SendNotificationForm
          fixedUserIds={[user.id]}
          onSuccess={() => {
            onOpenChange(false)
            onSuccess()
          }}
        />
      </DialogContent>
    </Dialog>
  )
}
