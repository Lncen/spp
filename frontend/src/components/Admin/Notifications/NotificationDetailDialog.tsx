import type { ReactNode } from "react"

import type { NotificationAdminItem } from "@/client"
import { formatDateTime } from "@/components/Admin/Automation/tasks/constants"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import {
  CHANNEL_LABELS,
  DELIVERY_STATUS_LABELS,
  sourceLabel,
} from "./constants"

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h3 className="text-sm font-semibold text-muted-foreground">{children}</h3>
  )
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid grid-cols-[84px_1fr] gap-3 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="break-words">{value}</span>
    </div>
  )
}

export function NotificationDetailDialog({
  item,
  onOpenChange,
}: {
  item: NotificationAdminItem | null
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Dialog open={item !== null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>通知详情</DialogTitle>
        </DialogHeader>
        {item && (
          <div className="space-y-5">
            <h2 className="text-xl font-bold tracking-tight">{item.title}</h2>
            <div className="space-y-1">
              <SectionTitle>内容</SectionTitle>
              <p className="whitespace-pre-line text-sm text-muted-foreground">
                {item.content || "—"}
              </p>
            </div>
            <Separator />
            <div className="space-y-2">
              <SectionTitle>基本信息</SectionTitle>
              <Row
                label="通知类型"
                value={<span className="font-mono">{item.event_type}</span>}
              />
              <Row label="来源" value={sourceLabel(item)} />
              <Row label="创建时间" value={formatDateTime(item.created_at)} />
            </div>
            <Separator />
            <div className="space-y-2">
              <SectionTitle>接收情况</SectionTitle>
              <Row label="接收用户" value={item.recipient ?? "—"} />
              <Row
                label="渠道"
                value={
                  CHANNEL_LABELS[item.delivery.channel] ?? item.delivery.channel
                }
              />
              <Row
                label="发送状态"
                value={
                  DELIVERY_STATUS_LABELS[item.delivery.status] ??
                  item.delivery.status
                }
              />
              <Row label="已读" value={item.read_at ? "是" : "否"} />
              <Row label="阅读时间" value={formatDateTime(item.read_at)} />
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
