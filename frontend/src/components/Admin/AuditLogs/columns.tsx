import type { ColumnDef } from "@tanstack/react-table"

import type { AuditLogPublic } from "@/client"
import { formatDateTime } from "@/components/Admin/Automation/tasks/constants"
import { Button } from "@/components/ui/button"

function changesSummary(changes: Record<string, unknown>): string {
  const keys = Object.keys(changes)
  if (keys.length === 0) return "—"
  return keys.slice(0, 3).join("、") + (keys.length > 3 ? "…" : "")
}

export function auditLogColumns(
  onView: (log: AuditLogPublic) => void,
): ColumnDef<AuditLogPublic>[] {
  return [
    {
      accessorKey: "actor_identifier",
      header: "操作者",
      cell: ({ row }) => (
        <span className="block max-w-[180px] truncate text-sm">
          {row.original.actor_identifier ?? "—"}
        </span>
      ),
    },
    {
      accessorKey: "action",
      header: "操作",
      cell: ({ row }) => (
        <span className="font-mono text-sm font-medium">
          {row.original.action}
        </span>
      ),
    },
    {
      id: "resource",
      header: "对象",
      cell: ({ row }) => (
        <span className="font-mono text-xs text-muted-foreground">
          {row.original.resource_type}
          {row.original.resource_id ? ` / ${row.original.resource_id}` : ""}
        </span>
      ),
    },
    {
      id: "changes",
      header: "变更字段",
      cell: ({ row }) => (
        <span className="block max-w-[220px] truncate text-sm text-muted-foreground">
          {changesSummary(row.original.changes)}
        </span>
      ),
    },
    {
      accessorKey: "ip",
      header: "IP",
      cell: ({ row }) => (
        <span className="font-mono text-xs text-muted-foreground">
          {row.original.ip ?? "—"}
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
