import type { ColumnDef } from "@tanstack/react-table"

import type { NotificationAdminItem } from "@/client"
import { formatDateTime } from "@/components/Admin/Automation/tasks/constants"
import { Badge } from "@/components/ui/badge"
import {
  CHANNEL_LABELS,
  DELIVERY_STATUS_BADGE_VARIANT,
  DELIVERY_STATUS_LABELS,
  sourceLabel,
} from "./constants"
import { NotificationActionsMenu } from "./NotificationActionsMenu"

export function notificationColumns(
  onView: (item: NotificationAdminItem) => void,
): ColumnDef<NotificationAdminItem>[] {
  return [
    {
      accessorKey: "event_type",
      header: "类型",
      cell: ({ row }) => (
        <span className="font-mono text-sm font-medium">
          {row.original.event_type}
        </span>
      ),
    },
    {
      accessorKey: "title",
      header: "标题",
      cell: ({ row }) => (
        <span
          className="block max-w-[260px] truncate text-sm"
          title={row.original.title}
        >
          {row.original.title}
        </span>
      ),
    },
    {
      accessorKey: "recipient",
      header: "接收对象",
      cell: ({ row }) => (
        <span className="block max-w-[180px] truncate text-sm text-muted-foreground">
          {row.original.recipient ?? "—"}
        </span>
      ),
    },
    {
      id: "source",
      header: "来源",
      cell: ({ row }) => (
        <span className="font-mono text-xs text-muted-foreground">
          {sourceLabel(row.original)}
        </span>
      ),
    },
    {
      id: "channel",
      header: "渠道",
      accessorFn: (row) => row.delivery.channel,
      cell: ({ row }) => (
        <Badge variant="outline">
          {CHANNEL_LABELS[row.original.delivery.channel] ??
            row.original.delivery.channel}
        </Badge>
      ),
    },
    {
      id: "status",
      header: "状态",
      accessorFn: (row) => row.delivery.status,
      cell: ({ row }) => (
        <Badge
          variant={DELIVERY_STATUS_BADGE_VARIANT[row.original.delivery.status]}
        >
          {DELIVERY_STATUS_LABELS[row.original.delivery.status] ??
            row.original.delivery.status}
        </Badge>
      ),
    },
    {
      accessorKey: "created_at",
      header: "时间",
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground">
          {formatDateTime(row.original.created_at)}
        </span>
      ),
    },
    {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <NotificationActionsMenu item={row.original} onView={onView} />
        </div>
      ),
    },
  ]
}
