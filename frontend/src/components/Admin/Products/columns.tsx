import type { ColumnDef } from "@tanstack/react-table"

import type { ProductPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import {
  PRODUCT_STATUS_BADGE_VARIANT,
  productStatusLabel,
  productTypeLabel,
  sourceTypeLabel,
} from "./constants"
import { ProductActionsMenu } from "./ProductActionsMenu"

function formatPrice(product: ProductPublic) {
  const pricing = product.pricing
  if (pricing?.fixed_price != null) {
    const precision = pricing.price_display_precision ?? 2
    return `${Number(pricing.fixed_price).toFixed(precision)}`
  }
  if (pricing?.item_coefficient != null) {
    return `系数 ${Number(pricing.item_coefficient).toFixed(2)}`
  }
  if (pricing?.price_template_id != null) {
    const precision = pricing.price_display_precision ?? 2
    return `${Number(pricing.cost_price).toFixed(precision)}`
  }
  return "未配置"
}

function formatLossPrice(product: ProductPublic) {
  const lossPrice = product.pricing?.loss_price
  if (lossPrice == null) {
    return "未配置"
  }
  const precision = product.pricing?.price_display_precision ?? 2
  return Number(lossPrice).toFixed(precision)
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
    accessorKey: "name",
    header: "商品名称",
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
    cell: ({ row }) => (
      <span className="text-sm text-muted-foreground">
        {row.original.category_name || "未分类"}
      </span>
    ),
  },
  {
    accessorKey: "type",
    header: "类型",
    cell: ({ row }) => (
      <span className="text-sm">{productTypeLabel(row.original.type)}</span>
    ),
  },
  {
    accessorKey: "status",
    header: "状态",
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
    accessorKey: "source_type",
    header: "来源",
    cell: ({ row }) => (
      <span className="text-sm">
        {sourceTypeLabel(row.original.source_type)}
      </span>
    ),
  },
  {
    id: "price",
    header: "成本价格",
    cell: ({ row }) => (
      <span className="font-mono text-sm">{formatPrice(row.original)}</span>
    ),
  },
  {
    id: "loss_price",
    header: "固定损耗",
    cell: ({ row }) => (
      <span className="font-mono text-sm">{formatLossPrice(row.original)}</span>
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
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <ProductActionsMenu product={row.original} />
      </div>
    ),
  },
]
