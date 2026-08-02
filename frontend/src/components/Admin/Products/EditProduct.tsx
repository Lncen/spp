import { Pencil } from "lucide-react"
import { useState } from "react"

import type { ProductPublic } from "@/client"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import ProductFormDialog from "./ProductForm"

interface EditProductProps {
  product: ProductPublic
  onSuccess: () => void
}

const EditProduct = ({ product, onSuccess }: EditProductProps) => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Pencil />
        编辑商品
      </DropdownMenuItem>
      <ProductFormDialog
        product={product}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
        onSuccess={onSuccess}
      />
    </>
  )
}

export default EditProduct
