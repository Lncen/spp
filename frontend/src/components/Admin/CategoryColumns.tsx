import type { ColumnDef } from "@tanstack/react-table"
import type { ImageCategoryPublic } from "@/client"
import { cn } from "@/lib/utils"
import { CategoryActionsMenu } from "./CategoryActionsMenu"
export const categoryColumns: ColumnDef<ImageCategoryPublic>[] = [
  {
    accessorKey: "name",
    header: "标识",
    cell: ({ row }) => (
      <span className="font-mono text-sm font-medium">{row.original.name}</span>
    ),
  },
  {
    accessorKey: "description",
    header: "描述",
    cell: ({ row }) => (
      <span className={cn("text-muted-foreground", !row.original.description && "italic")}>
        {row.original.description || "无描述"}
      </span>
    ),
  },
  {
    accessorKey: "image_count",
    header: "图片数",
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.image_count}</span>
    ),
  },
  {
    accessorKey: "sort_order",
    header: "排序",
    cell: ({ row }) => (
      <span className="text-muted-foreground">{row.original.sort_order ?? 0}</span>
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
        <span className={row.original.is_active ? "" : "text-muted-foreground"}>
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
        <CategoryActionsMenu category={row.original} />
      </div>
    ),
  },
]
