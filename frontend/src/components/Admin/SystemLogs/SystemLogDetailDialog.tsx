import type { ReactNode } from "react"

import type { SystemLogPublic } from "@/client"
import { formatDateTime } from "@/components/Admin/Automation/tasks/constants"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import {
  LOG_LEVEL_BADGE_VARIANT,
  LOG_LEVEL_LABELS,
  LOG_STATUS_BADGE_VARIANT,
  LOG_STATUS_LABELS,
} from "./constants"

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid grid-cols-[96px_1fr] gap-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="break-words">{value}</span>
    </div>
  )
}

function JsonBlock({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="space-y-1">
      <div className="text-sm font-semibold text-muted-foreground">{label}</div>
      <pre className="max-h-64 overflow-auto rounded-md border bg-muted/40 p-3 text-xs whitespace-pre-wrap break-all">
        {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}

export function SystemLogDetailDialog({
  log,
  onOpenChange,
}: {
  log: SystemLogPublic | null
  onOpenChange: (open: boolean) => void
}) {
  const status = log?.status ?? ""

  return (
    <Dialog open={log !== null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            系统日志详情 · <span className="font-mono">{log?.event_type}</span>
          </DialogTitle>
        </DialogHeader>
        {log && (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <Badge variant={LOG_LEVEL_BADGE_VARIANT[log.level]}>
                {LOG_LEVEL_LABELS[log.level] ?? log.level}
              </Badge>
              <Badge variant={LOG_STATUS_BADGE_VARIANT[status]}>
                {LOG_STATUS_LABELS[status] ?? status}
              </Badge>
            </div>
            <Separator />
            <div className="space-y-2">
              <Row label="模块" value={log.module} />
              <Row label="事件类型" value={log.event_type} />
              <Row
                label="关联对象"
                value={
                  log.resource_type
                    ? `${log.resource_type} / ${log.resource_id ?? "—"}`
                    : "—"
                }
              />
              <Row
                label="操作者"
                value={
                  log.actor_id
                    ? `${log.actor_type ?? "user"} / ${log.actor_id}`
                    : (log.actor_type ?? "—")
                }
              />
              <Row label="业务 ID" value={log.business_id ?? "—"} />
              <Row label="任务 ID" value={log.task_id ?? "—"} />
              <Row label="请求 ID" value={log.request_id ?? "—"} />
              <Row label="链路 ID" value={log.trace_id ?? "—"} />
              <Row label="事件 ID" value={log.event_id ?? "—"} />
              <Row label="错误码" value={log.error_code ?? "—"} />
              <Row label="错误信息" value={log.error_message ?? "—"} />
              <Row label="时间" value={formatDateTime(log.created_at)} />
            </div>
            <Separator />
            <JsonBlock label="上下文数据" value={log.context} />
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
