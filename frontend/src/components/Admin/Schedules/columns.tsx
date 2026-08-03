import type { ColumnDef } from "@tanstack/react-table"

import type { SchedulePublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { ScheduleActionsMenu } from "./ScheduleActionsMenu"

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

export const columns: ColumnDef<SchedulePublic>[] = [
  {
    accessorKey: "name",
    header: "计划名称",
    cell: ({ row }) => (
      <span className="max-w-[220px] truncate font-medium">
        {row.original.name}
      </span>
    ),
  },
  {
    accessorKey: "task",
    header: "任务",
    cell: ({ row }) => (
      <span
        className="block max-w-[260px] truncate font-mono text-xs"
        title={row.original.task}
      >
        {row.original.task}
      </span>
    ),
  },
  {
    accessorKey: "schedule_description",
    header: "调度规则",
    cell: ({ row }) => (
      <span className="block max-w-[260px] truncate text-sm text-muted-foreground">
        {row.original.schedule_description ?? "—"}
      </span>
    ),
  },
  {
    accessorKey: "enabled",
    header: "状态",
    cell: ({ row }) => {
      const enabled = row.original.enabled
      return (
        <Badge variant={enabled ? "default" : "secondary"}>
          {enabled ? "启用" : "停用"}
        </Badge>
      )
    },
  },
  {
    accessorKey: "last_run_at",
    header: "上次执行",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {formatDateTime(row.original.last_run_at)}
      </span>
    ),
  },
  {
    accessorKey: "total_run_count",
    header: "执行次数",
    cell: ({ row }) => (
      <span className="font-mono text-sm">{row.original.total_run_count}</span>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <ScheduleActionsMenu schedule={row.original} />
      </div>
    ),
  },
]
