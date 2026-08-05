import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Play, Square } from "lucide-react"
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

interface ToggleScheduleProps {
  schedule: SchedulePublic
  onSuccess: () => void
}

const ToggleSchedule = ({ schedule, onSuccess }: ToggleScheduleProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () => SchedulesService.toggleSchedule({ id: schedule.id }),
    onSuccess: (data) => {
      showSuccessToast(
        `计划任务已${data.enabled ? "启用" : "停用"}`,
      )
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        {schedule.enabled ? <Square /> : <Play />}
        {schedule.enabled ? "停用" : "启用"}
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{schedule.enabled ? "停用计划任务" : "启用计划任务"}</DialogTitle>
          <DialogDescription>
            确定要{schedule.enabled ? "停用" : "启用"}计划任务{" "}
            <strong>{schedule.name}</strong> 吗？
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="mt-4">
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              取消
            </Button>
          </DialogClose>
          <LoadingButton
            type="button"
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            确认
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default ToggleSchedule
