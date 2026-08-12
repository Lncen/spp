import type { ColumnDef } from "@tanstack/react-table"

import type { AutomationEventPublic } from "@/client"
import { formatDateTime } from "@/components/Admin/Automation/tasks/constants"
import { Badge } from "@/components/ui/badge"
import { EVENT_STATUS_BADGE_VARIANT, EVENT_STATUS_LABELS } from "./constants"
import { EventActionsMenu } from "./EventActionsMenu"

export const eventColumns: ColumnDef<AutomationEventPublic>[] = [
  {
    accessorKey: "event_type",
    header: "事件类型",
    cell: ({ row }) => (
      <span className="font-mono text-sm font-medium">
        {row.original.event_type}
      </span>
    ),
  },
  {
    accessorKey: "payload",
    header: "事件载荷",
    cell: ({ row }) => {
      const raw = JSON.stringify(row.original.payload)
      return (
        <span
          className="block max-w-[320px] truncate font-mono text-xs text-muted-foreground"
          title={raw}
        >
          {raw}
        </span>
      )
    },
  },
  {
    accessorKey: "status",
    header: "状态",
    cell: ({ row }) => (
      <Badge variant={EVENT_STATUS_BADGE_VARIANT[row.original.status]}>
        {EVENT_STATUS_LABELS[row.original.status]}
      </Badge>
    ),
  },
  {
    accessorKey: "dispatch_attempts",
    header: "分发次数",
    cell: ({ row }) => (
      <span className="font-mono text-sm">
        {row.original.dispatch_attempts}
      </span>
    ),
  },
  {
    accessorKey: "last_error",
    header: "错误信息",
    cell: ({ row }) => (
      <span
        className="block max-w-[220px] truncate text-sm text-destructive"
        title={row.original.last_error ?? ""}
      >
        {row.original.last_error ?? "—"}
      </span>
    ),
  },
  {
    accessorKey: "processing_at",
    header: "处理时间",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {formatDateTime(row.original.processing_at)}
      </span>
    ),
  },
  {
    accessorKey: "dispatched_at",
    header: "分发完成",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {formatDateTime(row.original.dispatched_at)}
      </span>
    ),
  },
  {
    accessorKey: "next_dispatch_at",
    header: "下次分发",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {formatDateTime(row.original.next_dispatch_at)}
      </span>
    ),
  },
  {
    accessorKey: "created_at",
    header: "发布时间",
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
        <EventActionsMenu event={row.original} />
      </div>
    ),
  },
]
