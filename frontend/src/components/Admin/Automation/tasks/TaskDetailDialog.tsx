import { useMutation, useQueryClient } from "@tanstack/react-query"
import { type ReactNode, useState } from "react"

import type {
  AutomationTaskArchivePublic,
  AutomationTaskPublic,
  AutomationTaskStatus,
} from "@/client"
import { AutomationService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { formatDateTime, TASK_STATUS_LABELS } from "./constants"

interface TaskDetailDialogProps {
  task: AutomationTaskPublic | AutomationTaskArchivePublic
}

const STATUS_DOT: Record<AutomationTaskStatus, string> = {
  pending: "bg-muted-foreground",
  running: "bg-blue-500",
  success: "bg-emerald-500",
  failed: "bg-red-500",
  canceled: "bg-muted-foreground",
}

function DetailRow({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="text-right">{children}</span>
    </div>
  )
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="space-y-1">
      <div className="text-sm font-medium">{label}</div>
      <pre className="max-h-48 overflow-auto rounded-md border bg-muted/40 p-3 text-xs whitespace-pre-wrap break-all">
        {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}

export const TaskDetailDialog = ({ task }: TaskDetailDialogProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const cancelMutation = useMutation({
    mutationFn: () => AutomationService.cancelAutomationTask({ id: task.id }),
    onSuccess: () => {
      showSuccessToast("任务已取消")
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["automation-tasks"] })
      queryClient.invalidateQueries({ queryKey: ["automation-archives"] })
    },
  })

  const retryMutation = useMutation({
    mutationFn: () => AutomationService.retryAutomationTask({ id: task.id }),
    onSuccess: () => {
      showSuccessToast("任务已重新进入队列")
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["automation-tasks"] })
      queryClient.invalidateQueries({ queryKey: ["automation-archives"] })
    },
  })

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        查看详情
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>任务详情</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="divide-y rounded-md border px-4">
            <DetailRow label="状态">
              <span className="inline-flex items-center gap-1.5">
                <span
                  className={`size-2 rounded-full ${STATUS_DOT[task.status]}`}
                />
                {TASK_STATUS_LABELS[task.status]}
              </span>
            </DetailRow>
            <DetailRow label="任务类型">
              <span className="font-mono text-sm">{task.task_type}</span>
            </DetailRow>
            <DetailRow label="任务 ID">
              <span className="font-mono text-xs break-all">{task.id}</span>
            </DetailRow>
            <DetailRow label="优先级">
              <span className="font-mono text-sm">{task.priority}</span>
            </DetailRow>
            <DetailRow label="重试次数">
              <span className="font-mono text-sm">
                {task.retry_count} / {task.max_retry}
              </span>
            </DetailRow>
            <DetailRow label="创建时间">
              {formatDateTime(task.created_at)}
            </DetailRow>
            <DetailRow label="开始时间">
              {formatDateTime(task.started_at)}
            </DetailRow>
          </div>
          <JsonBlock label="Payload" value={task.payload} />
          <div className="space-y-1.5">
            <div className="text-sm font-medium">来源</div>
            {task.event_id || task.rule_id ? (
              <div className="space-y-1 rounded-md border bg-muted/40 p-3 text-xs">
                <div>
                  <span className="text-muted-foreground">事件: </span>
                  <span className="font-mono">
                    {task.event_type_label ?? "—"}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">规则 : </span>
                  <span className="font-mono">{task.rule_name ?? "—"}</span>
                </div>
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">手动创建</div>
            )}
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => setIsOpen(false)}>
            关闭
          </Button>
          {task.status === "failed" && (
            <Button
              disabled={retryMutation.isPending}
              onClick={() => retryMutation.mutate()}
            >
              重新入队
            </Button>
          )}
          {task.status === "pending" && (
            <Button
              variant="destructive"
              disabled={cancelMutation.isPending}
              onClick={() => cancelMutation.mutate()}
            >
              取消任务
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default TaskDetailDialog
