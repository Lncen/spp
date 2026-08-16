import { useMutation } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import {
  Bell,
  EllipsisVertical,
  MessagesSquare,
  Pencil,
  ReceiptText,
  Trash2,
} from "lucide-react"
import { useState } from "react"

import { CustomerServiceService, type UserListItemPublic } from "@/client"
import { useCustomerService } from "@/components/CustomerService/CustomerServiceProvider"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useAuth from "@/hooks/useAuth"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import DeleteUser from "./DeleteUser"
import EditUser from "./EditUser"
import { SendUserNotificationDialog } from "./SendUserNotificationDialog"

interface UserActionsMenuProps {
  user: UserListItemPublic
}

export const UserActionsMenu = ({ user }: UserActionsMenuProps) => {
  const [open, setOpen] = useState(false)
  const [notifyOpen, setNotifyOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const { openConversation } = useCustomerService()
  const { user: currentUser } = useAuth()
  const { showErrorToast } = useCustomToast()

  const isCurrentUser = user.id === currentUser?.id

  // 先关闭菜单再打开 Dialog，避免两个焦点陷阱同时激活导致栈溢出
  const openAfterMenuClose = (setOpenDialog: (open: boolean) => void) => {
    setOpen(false)
    window.setTimeout(() => setOpenDialog(true), 50)
  }

  const startConversationMutation = useMutation({
    mutationFn: () =>
      CustomerServiceService.createConversationEndpoint({
        requestBody: { user_id: user.id },
      }),
    onSuccess: (conversation) => {
      setOpen(false)
      openConversation(conversation.id)
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <>
      <DropdownMenu open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon">
            <EllipsisVertical />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem asChild onSelect={(e) => e.preventDefault()}>
            <RouterLink to="/orders" search={{ user_id: user.id }}>
              <ReceiptText />
              查看订单
            </RouterLink>
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={isCurrentUser || startConversationMutation.isPending}
            onSelect={(event) => event.preventDefault()}
            onClick={() => startConversationMutation.mutate()}
          >
            <MessagesSquare />
            发起会话
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={isCurrentUser}
            onSelect={() => openAfterMenuClose(setNotifyOpen)}
          >
            <Bell />
            发送通知
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => openAfterMenuClose(setEditOpen)}>
            <Pencil />
            编辑用户
          </DropdownMenuItem>
          {!isCurrentUser && (
            <DropdownMenuItem
              variant="destructive"
              onSelect={() => openAfterMenuClose(setDeleteOpen)}
            >
              <Trash2 />
              删除用户
            </DropdownMenuItem>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      <SendUserNotificationDialog
        user={user}
        open={notifyOpen}
        onOpenChange={setNotifyOpen}
        onSuccess={() => setOpen(false)}
      />
      <EditUser
        user={user}
        open={editOpen}
        onOpenChange={setEditOpen}
        onSuccess={() => setOpen(false)}
      />
      {!isCurrentUser && (
        <DeleteUser
          id={user.id}
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          onSuccess={() => setOpen(false)}
        />
      )}
    </>
  )
}
