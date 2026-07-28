import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { ImagePublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Separator } from "@/components/ui/separator"
import DeleteImage from "./DeleteImage"
import EditImageCategory from "./EditImageCategory"

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B"
  const units = ["B", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  const size = bytes / Math.pow(1024, i)
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

interface ImageCardProps {
  image: ImagePublic
}

export const ImageCard = ({ image }: ImageCardProps) => {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="group relative flex flex-col overflow-hidden rounded-xl border bg-card shadow-sm transition-shadow hover:shadow-md">
      {/* Image preview area */}
      <div className="relative aspect-[4/3] overflow-hidden bg-muted">
        <img
          src={image.url}
          alt={image.filename}
          className="size-full object-cover transition-transform group-hover:scale-105"
        />
        {/* Actions overlay */}
        <div className="absolute right-2 top-2">
          <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
            <DropdownMenuTrigger asChild>
              <Button
                variant="secondary"
                size="icon"
                className="size-8 rounded-full opacity-0 shadow-sm transition-opacity group-hover:opacity-100 [&[data-state=open]]:opacity-100"
              >
                <EllipsisVertical className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DeleteImage id={image.id} onSuccess={() => setMenuOpen(false)} />
              <Separator className="my-1" />
              <EditImageCategory image={image} onSuccess={() => setMenuOpen(false)} />
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Info area */}
      <div className="flex flex-col gap-1 p-3">
        <p className="truncate text-sm font-medium" title={image.filename}>
          {image.filename}
        </p>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {image.category && (
            <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
              {image.category}
            </span>
          )}
          <span>{image.width} x {image.height}</span>
          <span className="text-border">|</span>
          <span>{formatFileSize(image.file_size)}</span>
        </div>
      </div>
    </div>
  )
}
