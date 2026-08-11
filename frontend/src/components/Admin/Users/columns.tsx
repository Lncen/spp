import type { ColumnDef } from "@tanstack/react-table"

import type { UserListItemPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { UserActionsMenu } from "./UserActionsMenu"

export type UserTableData = UserListItemPublic & {
  isCurrentUser: boolean
}

export const columns: ColumnDef<UserTableData>[] = [
  {
    accessorKey: "username",
    header: "用户名",
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <span className="font-medium">{row.original.username}</span>
        {row.original.isCurrentUser && (
          <Badge variant="outline" className="text-xs">
            你
          </Badge>
        )}
      </div>
    ),
  },
  {
    accessorKey: "balance",
    header: "余额",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {Number(row.original.balance).toFixed(2)}
      </span>
    ),
  },
  {
    accessorKey: "is_superuser",
    header: "角色",
    cell: ({ row }) => (
      <Badge variant={row.original.is_superuser ? "default" : "secondary"}>
        {row.original.is_superuser ? "超级管理员" : "用户"}
      </Badge>
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
        <UserActionsMenu user={row.original} />
      </div>
    ),
  },
]
