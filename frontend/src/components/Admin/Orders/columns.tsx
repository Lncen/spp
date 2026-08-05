import type { ColumnDef } from "@tanstack/react-table"

import type { OrderListItem } from "@/client"
import { Badge } from "@/components/ui/badge"
import OrderActionsMenu from "./OrderActionsMenu"
import {
  ORDER_STATUS_BADGE_VARIANT,
  orderStatusLabel,
} from "./constants"

function formatDateTime(value?: string | null) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { hour12: false })
}

export const columns: ColumnDef<OrderListItem>[] = [
  {
    accessorKey: "product_name",
    header: "名称",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {row.original.product_name}
      </span>
    ),
  },
  {
    accessorKey: "params",
    header: "订单参数",
    cell: ({ row }) => (
      <div className="max-w-56 space-y-0.5 break-all text-xs text-muted-foreground">
        {Object.entries(row.original.params).length > 0 ? (
          Object.entries(row.original.params).map(([key, value]) => (
            <div key={key}>
              <span className="font-medium text-foreground">{key}:</span>{" "}
              {String(value)}
            </div>
          ))
        ) : (
          "-"
        )}
      </div>
    ),
  },
  {
    accessorKey: "username",
    header: "用户",
    cell: ({ row }) => (
      <span className="font-medium">{row.original.username || "-"}</span>
    ),
  },
  {
    accessorKey: "status",
    header: "状态",
    cell: ({ row }) => (
      <Badge
        variant={
          ORDER_STATUS_BADGE_VARIANT[row.original.status] ?? "secondary"
        }
      >
        {orderStatusLabel(row.original.status)}
      </Badge>
    ),
  },
  {
    accessorKey: "total_amount",
    header: "金额",
    cell: ({ row }) => (
      <span className="font-mono text-sm">
        {Number(row.original.total_amount).toFixed(2)}
      </span>
    ),
  },
  {
    accessorKey: "quantity",
    header: "数量",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {row.original.quantity}
      </span>
    ),
  },
  {
    accessorKey: "created_at",
    header: "创建时间",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {formatDateTime(row.original.created_at)}
      </span>
    ),
  },
  {
    id: "actions",
    header: "操作",
    cell: ({ row }) => <OrderActionsMenu order={row.original} />,
  },
]
