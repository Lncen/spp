import type { ColumnDef } from "@tanstack/react-table"
import { ChevronRight } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import ProductCategoryActionsMenu from "./ProductCategoryActionsMenu"
import type { ProductCategoryRow } from "./types"

export const createProductCategoryColumns =
  (): ColumnDef<ProductCategoryRow>[] => [
    {
      accessorKey: "name",
      header: "名称",
      cell: ({ row }) => (
        <div
          className="flex items-center gap-1.5"
          style={{ paddingLeft: `${row.depth * 1.25}rem` }}
        >
          {row.getCanExpand() ? (
            <Button
              variant="ghost"
              size="icon"
              className="size-6 p-0"
              aria-label={row.getIsExpanded() ? "收起分类" : "展开分类"}
              onClick={row.getToggleExpandedHandler()}
            >
              <ChevronRight
                className={cn(
                  "size-4 transition-transform",
                  row.getIsExpanded() && "rotate-90",
                )}
              />
            </Button>
          ) : (
            <span className="inline-block size-6" />
          )}
          <span className="text-sm font-medium">{row.original.name}</span>
        </div>
      ),
    },
    {
      accessorKey: "icon_url",
      header: "图标",
      cell: ({ row }) =>
        row.original.icon_url ? (
          <img
            src={row.original.icon_url}
            alt={row.original.name}
            className="size-8 rounded object-cover"
          />
        ) : (
          <span className="text-muted-foreground">无</span>
        ),
    },
    {
      accessorKey: "product_count",
      header: "商品数",
      cell: ({ row }) => (
        <span className="text-muted-foreground">
          {row.original.product_count}
        </span>
      ),
    },
    {
      accessorKey: "sort",
      header: "排序",
      cell: ({ row }) => (
        <span className="text-muted-foreground">{row.original.sort}</span>
      ),
    },
    {
      accessorKey: "is_active",
      header: "状态",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "size-2 rounded-full",
              row.original.is_active ? "bg-green-500" : "bg-gray-400",
            )}
          />
          <span
            className={row.original.is_active ? "" : "text-muted-foreground"}
          >
            {row.original.is_active ? "启用" : "禁用"}
          </span>
        </div>
      ),
    },
    {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <ProductCategoryActionsMenu category={row.original} />
        </div>
      ),
    },
  ]
