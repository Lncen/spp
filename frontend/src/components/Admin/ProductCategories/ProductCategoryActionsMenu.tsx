import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { ProductCategoryPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteProductCategory from "./DeleteProductCategory"
import EditProductCategory from "./EditProductCategory"

interface ProductCategoryActionsMenuProps {
  category: ProductCategoryPublic
}

const ProductCategoryActionsMenu = ({
  category,
}: ProductCategoryActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditProductCategory
          category={category}
          onSuccess={() => setOpen(false)}
        />
        <DeleteProductCategory
          id={category.id}
          name={category.name}
          onSuccess={() => setOpen(false)}
        />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default ProductCategoryActionsMenu
