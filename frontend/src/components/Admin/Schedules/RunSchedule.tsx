import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Play } from "lucide-react"
import { useState } from "react"

import type { SchedulePublic } from "@/client"
import { SchedulesService } from "@/client"
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

interface RunScheduleProps {
  schedule: SchedulePublic
}

const RunSchedule = ({ schedule }: RunScheduleProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [taskId, setTaskId] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () => SchedulesService.runSchedule({ id: schedule.id }),
    onSuccess: (data) => {
      setTaskId(data.task_id)
      showSuccessToast(`任务已提交，ID: ${data.task_id}`)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] })
    },
  })

  const openDialog = () => {
    setTaskId(null)
    setIsOpen(true)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={openDialog}
      >
        <Play />
        立即执行
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>立即执行</DialogTitle>
          <DialogDescription>
            向 Celery 发送一次任务 <strong>{schedule.name}</strong>
            ，不影响原有调度。
          </DialogDescription>
        </DialogHeader>

        {taskId && (
          <div className="rounded-md border bg-muted/40 p-3 text-sm">
            <span className="text-muted-foreground">task_id: </span>
            <span className="font-mono">{taskId}</span>
          </div>
        )}

        <DialogFooter className="mt-4">
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              关闭
            </Button>
          </DialogClose>
          <LoadingButton
            type="button"
            loading={mutation.isPending}
            disabled={!!taskId}
            onClick={() => mutation.mutate()}
          >
            执行
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default RunSchedule
