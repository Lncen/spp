import type { ColumnDef } from "@tanstack/react-table"

import type { AutomationTaskArchivePublic } from "@/client"
import {
  formatDateTime,
  TASK_STATUS_BADGE_VARIANT,
  TASK_STATUS_LABELS,
} from "@/components/Admin/Automation/tasks/constants"
import { Badge } from "@/components/ui/badge"
import { ArchiveActionsMenu } from "./ArchiveActionsMenu"

export const archiveColumns: ColumnDef<AutomationTaskArchivePublic>[] = [
  {
    accessorKey: "task_type",
    header: "任务类型",
    cell: ({ row }) => (
      <span className="font-mono text-sm font-medium">
        {row.original.task_type}
      </span>
    ),
  },
  {
    accessorKey: "status",
    header: "状态",
    cell: ({ row }) => (
      <Badge variant={TASK_STATUS_BADGE_VARIANT[row.original.status]}>
        {TASK_STATUS_LABELS[row.original.status]}
      </Badge>
    ),
  },
  {
    accessorKey: "execute_at",
    header: "执行时间",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {formatDateTime(row.original.execute_at)}
      </span>
    ),
  },
  {
    accessorKey: "retry_count",
    header: "重试",
    cell: ({ row }) => (
      <span className="font-mono text-sm text-muted-foreground">
        {row.original.retry_count}/{row.original.max_retry}
      </span>
    ),
  },
  {
    accessorKey: "error_message",
    header: "错误信息",
    cell: ({ row }) => (
      <span
        className="block max-w-[220px] truncate text-sm text-destructive"
        title={row.original.error_message ?? ""}
      >
        {row.original.error_message ?? "—"}
      </span>
    ),
  },
  {
    accessorKey: "archived_at",
    header: "归档时间",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {formatDateTime(row.original.archived_at)}
      </span>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <ArchiveActionsMenu task={row.original} />
      </div>
    ),
  },
]
