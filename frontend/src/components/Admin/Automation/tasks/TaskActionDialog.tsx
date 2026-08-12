import { useMutation, useQueryClient } from "@tanstack/react-query"
import { RotateCcw, XCircle } from "lucide-react"
import { useState } from "react"

import type {
  AutomationTaskArchivePublic,
  AutomationTaskPublic,
} from "@/client"
import { AutomationService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface TaskActionDialogProps {
  task: AutomationTaskPublic | AutomationTaskArchivePublic
  action: "retry" | "cancel"
  onSuccess?: () => void
}

const ACTION_META = {
  retry: {
    title: "重试任务",
    description: "将失败任务重新加入执行队列，重试计数将重置。",
    confirm: "重试",
    icon: RotateCcw,
  },
  cancel: {
    title: "取消任务",
    description: "取消待执行任务，任务将进入已取消状态，不可恢复。",
    confirm: "取消任务",
    icon: XCircle,
  },
} as const

export const TaskActionDialog = ({
  task,
  action,
  onSuccess,
}: TaskActionDialogProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const meta = ACTION_META[action]
  const Icon = meta.icon

  const mutation = useMutation({
    mutationFn: () =>
      action === "retry"
        ? AutomationService.retryAutomationTask({ id: task.id })
        : AutomationService.cancelAutomationTask({ id: task.id }),
    onSuccess: () => {
      showSuccessToast(action === "retry" ? "任务已重新进入队列" : "任务已取消")
      setIsOpen(false)
      onSuccess?.()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["automation-tasks"] })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        variant={action === "cancel" ? "destructive" : "default"}
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Icon />
        {meta.confirm}
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{meta.title}</DialogTitle>
          <DialogDescription>
            {meta.description}
            <span className="mt-1 block font-mono text-xs break-all">
              {task.task_type} · {task.id}
            </span>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="mt-4">
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              取消
            </Button>
          </DialogClose>
          <LoadingButton
            variant={action === "cancel" ? "destructive" : "default"}
            type="button"
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {meta.confirm}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default TaskActionDialog
