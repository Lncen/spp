import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { ProductPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteProduct from "./DeleteProduct"
import EditProduct from "./EditProduct"

interface ProductActionsMenuProps {
  product: ProductPublic
}

export const ProductActionsMenu = ({ product }: ProductActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditProduct product={product} onSuccess={() => setOpen(false)} />
        <DeleteProduct
          id={product.id}
          name={product.name}
          onSuccess={() => setOpen(false)}
        />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default ProductActionsMenu
