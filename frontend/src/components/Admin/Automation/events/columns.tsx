import type { ColumnDef } from "@tanstack/react-table"

import type { AutomationEventPublic } from "@/client"
import { formatDateTime } from "@/components/Admin/Automation/tasks/constants"

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
    accessorKey: "created_at",
    header: "发布时间",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {formatDateTime(row.original.created_at)}
      </span>
    ),
  },
]
