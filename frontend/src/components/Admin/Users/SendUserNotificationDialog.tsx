import { Bell } from "lucide-react"
import { useState } from "react"

import type { UserListItemPublic } from "@/client"
import { SendNotificationForm } from "@/components/Admin/Notifications/SendNotificationForm"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"

interface SendUserNotificationDialogProps {
  user: UserListItemPublic
  /** 发送成功后关闭外层下拉菜单 */
  onSuccess: () => void
}

export const SendUserNotificationDialog = ({
  user,
  onSuccess,
}: SendUserNotificationDialogProps) => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Bell />
        发送通知
      </DropdownMenuItem>
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
            setIsOpen(false)
            onSuccess()
          }}
        />
      </DialogContent>
    </Dialog>
  )
}
