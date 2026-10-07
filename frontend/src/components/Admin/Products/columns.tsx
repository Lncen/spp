import type { ColumnDef } from "@tanstack/react-table"

import type { ProductPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import {
  PRODUCT_STATUS_BADGE_VARIANT,
  productStatusLabel,
  syncStatusLabel,
} from "./constants"
import { ProductActionsMenu } from "./ProductActionsMenu"
import { ProductFavoriteButton } from "./ProductFavoriteButton"

function formatSyncTime(value?: string | null): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  const diffMs = Date.now() - date.getTime()
  if (diffMs < 0) return "刚刚"
  const minutes = Math.floor(diffMs / 60_000)
  if (minutes < 1) return "刚刚"
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}天前`
  return date.toLocaleString("zh-CN", { hour12: false })
}

function formatPrice(product: ProductPublic) {
  const pricing = product.pricing
  const precision = pricing?.price_display_precision ?? 2
  const value = Number(pricing?.cost_price)
  return Number.isFinite(value) ? value.toFixed(precision) : "未配置"
}

function formatStock(product: ProductPublic) {
  const stock = product.inventory?.stock
  if (stock == null) {
    return "未配置"
  }
  return stock === -1 ? "无限" : String(stock)
}

export const columns: ColumnDef<ProductPublic>[] = [
  {
    id: "favorite",
    header: "收藏",
    // 列宽固定为图标按钮 + 单元格左右内边距，避免被表格自适应撑宽
    meta: { width: 64 },
    cell: ({ row }) => (
      <div className="flex justify-center">
        <ProductFavoriteButton productId={row.original.id} />
      </div>
    ),
  },
  {
    accessorKey: "name",
    header: "商品名称",
    meta: { width: 164 },
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <span className="font-medium">{row.original.name}</span>
        {row.original.is_closed && <Badge variant="outline">已关闭</Badge>}
      </div>
    ),
  },
  {
    accessorKey: "category_name",
    header: "分类",
    meta: { width: 64 },
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {row.original.category_name || "未分类"}
      </span>
    ),
  },
  {
    accessorKey: "supplier_name",
    header: "供应商",
     meta: { width: 32 },
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {row.original.supplier?.supplier_name || "—"}
      </span>
    ),
  },
  // {
  //   accessorKey: "type",
  //   header: "类型",
  //   cell: ({ row }) => (
  //     <span className="text-sm">{productTypeLabel(row.original.type)}</span>
  //   ),
  // },
  {
    accessorKey: "status",
    header: "状态",
     meta: { width: 32 },
    cell: ({ row }) => (
      <Badge
        variant={
          PRODUCT_STATUS_BADGE_VARIANT[row.original.status] ?? "secondary"
        }
      >
        {productStatusLabel(row.original.status)}
      </Badge>
    ),
  },
  {
    id: "price",
    header: "价格",
    cell: ({ row }) => (
      <span className="font-mono text-sm">{formatPrice(row.original)}</span>
    ),
  },
  {
    id: "stock",
    header: "库存",
    cell: ({ row }) => (
      <span className="text-sm">{formatStock(row.original)}</span>
    ),
  },
  {
    accessorKey: "sync_status",
    header: "同步",
    cell: ({ row }) => {
      const status = row.original.sync_status
      const isError = status === 2 // 按你实际的异常值改

      return (
        <span
          className={`text-sm ${isError ? "text-red-600" : "text-green-600"}`}
        >
          {syncStatusLabel(status)}
        </span>
      )
    },
  },
  {
    accessorKey: "synced_at",
    header: "同步时间",
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {formatSyncTime(row.original.synced_at)}
      </span>
    ),
  },

  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <ProductActionsMenu product={row.original} />
      </div>
    ),
  },
]
