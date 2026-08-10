import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { AutomationTaskPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import TaskActionDialog from "./TaskActionDialog"
import TaskDetailDialog from "./TaskDetailDialog"

interface TaskActionsMenuProps {
  task: AutomationTaskPublic
}

export const TaskActionsMenu = ({ task }: TaskActionsMenuProps) => {
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
        {task.status === "pending" && (
          <TaskActionDialog
            task={task}
            action="cancel"
            onSuccess={() => setOpen(false)}
          />
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default TaskActionsMenu
