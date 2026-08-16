import type { ColumnDef } from "@tanstack/react-table"

import type { SystemLogPublic } from "@/client"
import { formatDateTime } from "@/components/Admin/Automation/tasks/constants"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  LOG_LEVEL_BADGE_VARIANT,
  LOG_LEVEL_LABELS,
  LOG_STATUS_BADGE_VARIANT,
  LOG_STATUS_LABELS,
} from "./constants"

function resourceLabel(log: SystemLogPublic): string {
  if (!log.resource_type) return "—"
  return [log.resource_type, log.resource_id].filter(Boolean).join(" / ")
}

export function systemLogColumns(
  onView: (log: SystemLogPublic) => void,
): ColumnDef<SystemLogPublic>[] {
  return [
    {
      accessorKey: "level",
      header: "级别",
      cell: ({ row }) => (
        <Badge variant={LOG_LEVEL_BADGE_VARIANT[row.original.level]}>
          {LOG_LEVEL_LABELS[row.original.level] ?? row.original.level}
        </Badge>
      ),
    },
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
      accessorKey: "module",
      header: "模块",
      cell: ({ row }) => <Badge variant="outline">{row.original.module}</Badge>,
    },
    {
      id: "resource",
      header: "关联对象",
      cell: ({ row }) => (
        <span className="font-mono text-xs text-muted-foreground">
          {resourceLabel(row.original)}
        </span>
      ),
    },
    {
      accessorKey: "status",
      header: "结果",
      cell: ({ row }) => {
        const status = row.original.status ?? ""
        return (
          <Badge variant={LOG_STATUS_BADGE_VARIANT[status]}>
            {LOG_STATUS_LABELS[status] ?? status}
          </Badge>
        )
      },
    },
    {
      id: "error",
      header: "错误",
      accessorFn: (row) => row.error_message ?? row.error_code ?? "",
      cell: ({ row }) => (
        <span
          className="block max-w-[220px] truncate text-xs text-destructive"
          title={row.original.error_message ?? row.original.error_code ?? ""}
        >
          {row.original.error_message ?? row.original.error_code ?? "—"}
        </span>
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
          <Button
            variant="outline"
            size="sm"
            onClick={() => onView(row.original)}
          >
            详情
          </Button>
        </div>
      ),
    },
  ]
}
