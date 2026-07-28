import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { ImagePublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteImage from "./DeleteImage"
import EditImageCategory from "./EditImageCategory"

interface ImageActionsMenuProps {
  image: ImagePublic
}

export const ImageActionsMenu = ({ image }: ImageActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DeleteImage id={image.id} onSuccess={() => setOpen(false)} />
        <EditImageCategory image={image} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
