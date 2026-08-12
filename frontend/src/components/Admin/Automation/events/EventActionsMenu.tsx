import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { AutomationEventPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import EventDetailDialog from "./EventDetailDialog"

interface EventActionsMenuProps {
  event: AutomationEventPublic
}

export const EventActionsMenu = ({ event }: EventActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EventDetailDialog event={event} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default EventActionsMenu
