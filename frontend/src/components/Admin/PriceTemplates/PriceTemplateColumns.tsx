import type { ColumnDef } from "@tanstack/react-table"

import type { PriceTemplatePublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { PriceTemplateActionsMenu } from "./PriceTemplateActionsMenu"

export const priceTemplateColumns: ColumnDef<PriceTemplatePublic>[] = [
  {
    accessorKey: "name",
    header: "模板名称",
    cell: ({ row }) => (
      <span className="font-medium">{row.original.name}</span>
    ),
  },
  {
    accessorKey: "description",
    header: "描述",
    cell: ({ row }) => (
      <span
        className={cn(
          "block max-w-[240px] truncate text-muted-foreground",
          !row.original.description && "italic",
        )}
        title={row.original.description ?? undefined}
      >
        {row.original.description || "无描述"}
      </span>
    ),
  },
  {
    accessorKey: "is_active",
    header: "状态",
    cell: ({ row }) => (
      <Badge variant={row.original.is_active ? "default" : "secondary"}>
        {row.original.is_active ? "启用" : "禁用"}
      </Badge>
    ),
  },
  {
    accessorKey: "rules",
    header: "等级折扣",
    cell: ({ row }) => {
      const rules = [...row.original.rules].sort(
        (a, b) => a.level - b.level,
      )
      if (rules.length === 0) {
        return <span className="italic text-muted-foreground">未设置</span>
      }
      return (
        <div className="flex min-w-[280px] flex-wrap gap-1">
          {rules.map((rule) => (
            <Badge
              key={rule.id}
              variant="outline"
              className="font-mono text-[11px]"
            >
              L{rule.level} {Number(rule.discount_rate).toFixed(4)}
            </Badge>
          ))}
        </div>
      )
    },
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <PriceTemplateActionsMenu template={row.original} />
      </div>
    ),
  },
]
