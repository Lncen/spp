import { Link as RouterLink } from "@tanstack/react-router"
import { EllipsisVertical, ReceiptText } from "lucide-react"
import { useState } from "react"

import type { UserPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useAuth from "@/hooks/useAuth"
import DeleteUser from "./DeleteUser"
import EditUser from "./EditUser"

interface UserActionsMenuProps {
  user: UserPublic
}

export const UserActionsMenu = ({ user }: UserActionsMenuProps) => {
  const [open, setOpen] = useState(false)
  const { user: currentUser } = useAuth()

  const isCurrentUser = user.id === currentUser?.id

  return (
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
        <EditUser user={user} onSuccess={() => setOpen(false)} />
        {!isCurrentUser && (
          <DeleteUser id={user.id} onSuccess={() => setOpen(false)} />
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
