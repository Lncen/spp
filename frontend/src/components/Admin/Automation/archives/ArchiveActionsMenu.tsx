import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { AutomationTaskArchivePublic } from "@/client"
import TaskActionDialog from "@/components/Admin/Automation/tasks/TaskActionDialog"
import TaskDetailDialog from "@/components/Admin/Automation/tasks/TaskDetailDialog"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

interface ArchiveActionsMenuProps {
  task: AutomationTaskArchivePublic
}

export const ArchiveActionsMenu = ({ task }: ArchiveActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <TaskDetailDialog task={task} />
        {task.status === "failed" && (
          <TaskActionDialog
            task={task}
            action="retry"
            onSuccess={() => setOpen(false)}
          />
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default ArchiveActionsMenu
