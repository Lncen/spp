import type { ColumnDef } from "@tanstack/react-table"

import type { AutomationRulePublic } from "@/client"
import { formatDateTime } from "@/components/Admin/Automation/tasks/constants"
import { Badge } from "@/components/ui/badge"
import { RuleActionsMenu } from "./RuleActionsMenu"

export const ruleColumns: ColumnDef<AutomationRulePublic>[] = [
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
    accessorKey: "action_type",
    header: "动作类型",
    cell: ({ row }) => (
      <span className="font-mono text-sm">{row.original.action_type}</span>
    ),
  },
  {
    accessorKey: "config",
    header: "配置",
    cell: ({ row }) => {
      const raw = JSON.stringify(row.original.config)
      return (
        <span
          className="block max-w-[240px] truncate font-mono text-xs text-muted-foreground"
          title={raw}
        >
          {raw === "{}" ? "—" : raw}
        </span>
      )
    },
  },
  {
    accessorKey: "is_active",
    header: "状态",
    cell: ({ row }) => (
      <Badge variant={row.original.is_active ? "default" : "secondary"}>
        {row.original.is_active ? "启用" : "停用"}
      </Badge>
    ),
  },
  {
    accessorKey: "updated_at",
    header: "更新时间",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {formatDateTime(row.original.updated_at)}
      </span>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <RuleActionsMenu rule={row.original} />
      </div>
    ),
  },
]
