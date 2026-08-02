import type { ColumnDef } from "@tanstack/react-table"

import type { ImagePublic } from "@/client"
import { ImageActionsMenu } from "./ImageActionsMenu"

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B"
  const units = ["B", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const size = bytes / 1024 ** i
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

export const columns: ColumnDef<ImagePublic>[] = [
  {
    accessorKey: "url",
    header: "Preview",
    cell: ({ row }) => (
      <img
        src={row.original.url}
        alt={row.original.filename}
        className="size-10 rounded-md object-cover border"
      />
    ),
  },
  {
    accessorKey: "filename",
    header: "Filename",
    cell: ({ row }) => (
      <span className="font-medium">{row.original.filename}</span>
    ),
  },
  {
    accessorKey: "file_size",
    header: "File Size",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {formatFileSize(row.original.file_size)}
      </span>
    ),
  },
  {
    accessorKey: "width",
    header: "Dimensions",
    cell: ({ row }) => (
      <span className="text-muted-foreground">
        {row.original.width} × {row.original.height}
      </span>
    ),
  },
  {
    accessorKey: "created_at",
    header: "Created",
    cell: ({ row }) => {
      const date = row.original.created_at
      return (
        <span className="text-muted-foreground">
          {date
            ? new Date(date).toLocaleDateString("zh-CN", {
                year: "numeric",
                month: "short",
                day: "numeric",
              })
            : "—"}
        </span>
      )
    },
  },
  {
    id: "actions",
    header: () => <span className="sr-only">Actions</span>,
    cell: ({ row }) => (
      <div className="flex justify-end">
        <ImageActionsMenu image={row.original} />
      </div>
    ),
  },
]
