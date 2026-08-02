import type { ColumnDef } from "@tanstack/react-table"

import type { LevelPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { LevelActionsMenu } from "./LevelActionsMenu"

export const levelColumns: ColumnDef<LevelPublic>[] = [
  {
    accessorKey: "level",
    header: "编号",
    cell: ({ row }) => (
      <span className="font-mono text-sm font-medium">
        {row.original.level}
      </span>
    ),
  },
  {
    accessorKey: "name",
    header: "名称",
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  },
  {
    accessorKey: "description",
    header: "描述",
    cell: ({ row }) => (
      <span
        className={cn(
          "text-muted-foreground",
          !row.original.description && "italic",
        )}
      >
        {row.original.description || "无描述"}
      </span>
    ),
  },
  {
    accessorKey: "is_default",
    header: "默认",
    cell: ({ row }) => (
      <Badge variant={row.original.is_default ? "default" : "secondary"}>
        {row.original.is_default ? "默认" : "否"}
      </Badge>
    ),
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <LevelActionsMenu level={row.original} />
      </div>
    ),
  },
]
