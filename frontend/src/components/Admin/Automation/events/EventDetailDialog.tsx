import { useState } from "react"

import type { AutomationEventPublic } from "@/client"
import { formatDateTime } from "@/components/Admin/Automation/tasks/constants"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { EVENT_STATUS_BADGE_VARIANT, EVENT_STATUS_LABELS } from "./constants"

interface EventDetailDialogProps {
  event: AutomationEventPublic
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

export const EventDetailDialog = ({ event }: EventDetailDialogProps) => {
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
            事件详情 · <span className="font-mono">{event.event_type}</span>
          </DialogTitle>
          <DialogDescription>
            <Badge variant={EVENT_STATUS_BADGE_VARIANT[event.status]}>
              {EVENT_STATUS_LABELS[event.status]}
            </Badge>
            <span className="ml-2">
              创建于 {formatDateTime(event.created_at)}
            </span>
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <div className="text-muted-foreground">ID</div>
              <div className="font-mono text-xs break-all">{event.id}</div>
            </div>
            <div>
              <div className="text-muted-foreground">事件类型</div>
              <div className="font-mono">{event.event_type}</div>
            </div>
            <div>
              <div className="text-muted-foreground">分发次数</div>
              <div className="font-mono">{event.dispatch_attempts}</div>
            </div>
            <div>
              <div className="text-muted-foreground">处理时间</div>
              <div>{formatDateTime(event.processing_at)}</div>
            </div>
            <div>
              <div className="text-muted-foreground">分发完成</div>
              <div>{formatDateTime(event.dispatched_at)}</div>
            </div>
            <div>
              <div className="text-muted-foreground">下次分发</div>
              <div>{formatDateTime(event.next_dispatch_at)}</div>
            </div>
          </div>
          {event.last_error && (
            <div className="space-y-1">
              <div className="text-sm font-medium">错误信息</div>
              <pre className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-xs whitespace-pre-wrap break-all">
                {event.last_error}
              </pre>
            </div>
          )}
          <JsonBlock label="payload" value={event.payload} />
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

export default EventDetailDialog
