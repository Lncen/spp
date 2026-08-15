import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { SchedulePublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import EditSchedule from "./EditSchedule"
import RunSchedule from "./RunSchedule"
import ToggleSchedule from "./ToggleSchedule"

interface ScheduleActionsMenuProps {
  schedule: SchedulePublic
}

export const ScheduleActionsMenu = ({ schedule }: ScheduleActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditSchedule schedule={schedule} onSuccess={() => setOpen(false)} />
        <ToggleSchedule schedule={schedule} onSuccess={() => setOpen(false)} />
        <RunSchedule schedule={schedule} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default ScheduleActionsMenu
