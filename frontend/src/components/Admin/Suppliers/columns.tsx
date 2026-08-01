import type { ColumnDef } from "@tanstack/react-table"

import type { SupplierPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { SuppliersActionsMenu } from "./SupplierActionsMenu"

export const columns: ColumnDef<SupplierPublic>[] = [
  {
    accessorKey: "name",
    header: "名称",
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <span className="font-medium">{row.original.name}</span>
      </div>
    ),
  },
  {
    accessorKey: "platform",
    header: "平台",
    cell: ({ row }) => (
      <Badge variant="outline" className="font-mono text-xs">
        {row.original.platform}
      </Badge>
    ),
  },
  {
    accessorKey: "base_url",
    header: "接口地址",
    cell: ({ row }) => (
      <span className="max-w-[200px] truncate block text-muted-foreground text-sm" title={row.original.base_url}>
        {row.original.base_url}
      </span>
    ),
  },
  {
    accessorKey: "status",
    header: "状态",
    cell: ({ row }) => {
      const status = row.original.status
      return (
        <Badge
          variant={
            status === "active"
              ? "default"
              : status === "suspended"
                ? "destructive"
                : "secondary"
          }
        >
          {status === "active" ? "启用" : status === "inactive" ? "停用" : "冻结"}
        </Badge>
      )
    },
  },
  {
    accessorKey: "connection_status",
    header: "连接",
    cell: ({ row }) => {
      const conn = row.original.connection_status
      return (
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "size-2 rounded-full",
              conn === "online" && "bg-green-500",
              conn === "offline" && "bg-red-500",
              conn === "unknown" && "bg-yellow-500",
            )}
          />
          <span className="text-sm">{conn === "online" ? "在线" : conn === "offline" ? "离线" : "未知"}</span>
        </div>
      )
    },
  },
  {
    accessorKey: "balance",
    header: "余额",
    cell: ({ row }) => {
      const balance = row.original.balance
      return (
        <span className={cn("font-mono text-sm", balance == null && "text-muted-foreground")}>
          {balance != null ? balance.toString() : "—"}
        </span>
      )
    },
  },
  {
    accessorKey: "timeout_seconds",
    header: "超时",
    cell: ({ row }) => (
      <span className="text-muted-foreground text-sm">{row.original.timeout_seconds}s</span>
    ),
  },
  {
    accessorKey: "retry_times",
    header: "重试次数",
    cell: ({ row }) => (
      <span className="text-muted-foreground text-sm">{row.original.retry_times}</span>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <SuppliersActionsMenu supplier={row.original} />
      </div>
    ),
  },
]
