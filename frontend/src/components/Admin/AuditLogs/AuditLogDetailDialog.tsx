import type { ReactNode } from "react"

import type { AuditLogPublic } from "@/client"
import { formatDateTime } from "@/components/Admin/Automation/tasks/constants"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"

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

export function AuditLogDetailDialog({
  log,
  onOpenChange,
}: {
  log: AuditLogPublic | null
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Dialog open={log !== null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            操作审计详情 · <span className="font-mono">{log?.action}</span>
          </DialogTitle>
        </DialogHeader>
        {log && (
          <div className="space-y-4">
            <div className="space-y-2">
              <Row label="操作者" value={log.actor_identifier ?? "—"} />
              <Row
                label="操作"
                value={<span className="font-mono">{log.action}</span>}
              />
              <Row
                label="对象"
                value={
                  log.resource_id
                    ? `${log.resource_type} / ${log.resource_id}`
                    : log.resource_type
                }
              />
              <Row label="IP" value={log.ip ?? "—"} />
              <Row label="User-Agent" value={log.user_agent ?? "—"} />
              <Row label="请求 ID" value={log.request_id ?? "—"} />
              <Row label="事件 ID" value={log.event_id ?? "—"} />
              <Row label="时间" value={formatDateTime(log.created_at)} />
            </div>
            <Separator />
            <JsonBlock label="变更字段" value={log.changes} />
            <div className="grid gap-4 md:grid-cols-2">
              <JsonBlock label="操作前" value={log.before} />
              <JsonBlock label="操作后" value={log.after} />
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
