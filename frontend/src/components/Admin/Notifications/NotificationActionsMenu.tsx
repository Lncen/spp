import { EllipsisVertical, Eye } from "lucide-react"
import { useState } from "react"

import type { NotificationAdminItem } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { DeleteNotificationButton } from "./DeleteNotificationButton"
import { RetryDeliveryButton } from "./RetryDeliveryButton"

interface NotificationActionsMenuProps {
  item: NotificationAdminItem
  onView: (item: NotificationAdminItem) => void
}

export function NotificationActionsMenu({
  item,
  onView,
}: NotificationActionsMenuProps) {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onSelect={() => onView(item)}>
          <Eye />
          查看
        </DropdownMenuItem>
        {item.delivery.status === "failed" && (
          <RetryDeliveryButton deliveryId={item.delivery.id} />
        )}
        <DeleteNotificationButton
          notificationId={item.notification_id}
          title={item.title}
          onSuccess={() => setOpen(false)}
        />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
