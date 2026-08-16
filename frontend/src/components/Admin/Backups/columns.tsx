import type { ColumnDef } from "@tanstack/react-table"

import type { BackupPublic } from "@/client"
import { formatDateTime } from "@/components/Admin/Automation/tasks/constants"
import { Button } from "@/components/ui/button"

function formatSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

function countsLabel(backup: BackupPublic): string {
  const { counts } = backup
  return [
    `用户 ${counts.users}`,
    `钱包 ${counts.wallets}`,
    `订单 ${counts.orders}`,
    `参数 ${counts.order_params}`,
    `供应商 ${counts.suppliers}`,
  ].join(" · ")
}

export function backupColumns({
  onDownload,
  onRestore,
  onDelete,
}: {
  onDownload: (backup: BackupPublic) => void
  onRestore: (backup: BackupPublic) => void
  onDelete: (backup: BackupPublic) => void
}): ColumnDef<BackupPublic>[] {
  return [
    {
      accessorKey: "filename",
      header: "备份文件",
      cell: ({ row }) => (
        <span className="font-mono text-sm font-medium">
          {row.original.filename}
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
      id: "counts",
      header: "数据量",
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground">
          {countsLabel(row.original)}
        </span>
      ),
    },
    {
      accessorKey: "size",
      header: "大小",
      cell: ({ row }) => (
        <span className="text-sm tabular-nums text-muted-foreground">
          {formatSize(row.original.size)}
        </span>
      ),
    },
    {
      id: "actions",
      header: () => <span className="sr-only">Actions</span>,
      cell: ({ row }) => (
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onDownload(row.original)}
          >
            下载
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onRestore(row.original)}
          >
            恢复
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive"
            onClick={() => onDelete(row.original)}
          >
            删除
          </Button>
        </div>
      ),
    },
  ]
}
