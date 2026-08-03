import type { ColumnDef } from "@tanstack/react-table"

import type { OrderPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
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

export const columns: ColumnDef<OrderPublic>[] = [
  {
    accessorKey: "order_no",
    header: "订单号",
    cell: ({ row }) => (
      <span className="font-mono text-xs">{row.original.order_no}</span>
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
        {Number(row.original.total_amount).toFixed(2)} {row.original.currency}
      </span>
    ),
  },
  {
    accessorKey: "items",
    header: "商品数",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {row.original.items?.length ?? "-"}
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
]
