import { useState } from "react"

import type { AutomationTaskPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { formatDateTime, TASK_STATUS_LABELS } from "./constants"

interface TaskDetailDialogProps {
  task: AutomationTaskPublic
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

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        查看详情
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            任务详情 · <span className="font-mono">{task.task_type}</span>
          </DialogTitle>
          <DialogDescription>
            {TASK_STATUS_LABELS[task.status]} · 创建于{" "}
            {formatDateTime(task.created_at)}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-muted-foreground">ID</div>
              <div className="font-mono text-xs break-all">{task.id}</div>
            </div>
            <div>
              <div className="text-muted-foreground">执行时间</div>
              <div>{formatDateTime(task.execute_at)}</div>
            </div>
            <div>
              <div className="text-muted-foreground">优先级</div>
              <div className="font-mono">{task.priority}</div>
            </div>
            <div>
              <div className="text-muted-foreground">重试</div>
              <div className="font-mono">
                {task.retry_count}/{task.max_retry}
              </div>
            </div>
          </div>
          {task.error_message && (
            <div className="space-y-1">
              <div className="text-sm font-medium">错误信息</div>
              <pre className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-xs whitespace-pre-wrap break-all">
                {task.error_message}
              </pre>
            </div>
          )}
          <JsonBlock label="payload" value={task.payload} />
        </div>
        <div className="flex justify-end">
          <Button variant="outline" onClick={() => setIsOpen(false)}>
            关闭
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default TaskDetailDialog
