import type { ColumnDef } from "@tanstack/react-table"

import type { OrderListItem, OrderStatus } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { ORDER_STATUS_BADGE_VARIANT, orderStatusLabel } from "./constants"
import OrderActionsMenu from "./OrderActionsMenu"

const COMPLETED_STATUS: OrderStatus = 6
const CANCELED_STATUS: OrderStatus = 7
const REFUNDED_STATUS: OrderStatus = 8

function formatDateTime(value?: string | null) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { hour12: false })
}

/**
 * 订单完成度（0-100）：已完成数量 = 当前数量 - 开始数量，与后端退款公式一致。
 * 终态订单直接按状态返回，避免卡密类订单（数量快照不变化）恒为 0%。
 */
function orderProgress(order: OrderListItem): number | null {
  if (order.quantity <= 0) return null
  if (order.status === COMPLETED_STATUS) return 100
  if (order.status === CANCELED_STATUS || order.status === REFUNDED_STATUS) {
    return 0
  }
  const fulfilled = order.current_quantity - order.start_quantity
  const ratio = Math.min(Math.max(fulfilled / order.quantity, 0), 1)
  return Math.round(ratio * 100)
}

export const columns: ColumnDef<OrderListItem>[] = [
  {
    accessorKey: "product_name",
    header: "商品名称",
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
        {Object.entries(row.original.params).length > 0
          ? Object.entries(row.original.params).map(([key, value]) => (
              <div key={key}>{String(value)}</div>
            ))
          : "-"}
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
        variant={ORDER_STATUS_BADGE_VARIANT[row.original.status] ?? "secondary"}
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
        {Number(row.original.total_amount).toFixed(7)}
      </span>
    ),
  },
  {
    id: "progress",
    header: "完成度",
    cell: ({ row }) => {
      const progress = orderProgress(row.original)
      if (progress === null) {
        return <span className="text-sm text-muted-foreground">-</span>
      }
      return (
        <div className="flex items-center gap-2">
          <Progress value={progress} className="w-16" />
          <span className="text-xs text-muted-foreground tabular-nums">
            {progress}%
          </span>
        </div>
      )
    },
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
