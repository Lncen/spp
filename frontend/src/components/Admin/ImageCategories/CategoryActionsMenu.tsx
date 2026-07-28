import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { ImageCategoryPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteCategory from "./DeleteCategory"
import EditCategory from "./EditCategory"

interface CategoryActionsMenuProps {
  category: ImageCategoryPublic
}

export const CategoryActionsMenu = ({ category }: CategoryActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditCategory category={category} onSuccess={() => setOpen(false)} />
        <DeleteCategory id={category.id} name={category.name} onSuccess={() => setOpen(false)} />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
