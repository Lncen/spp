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
        onSelect={() => {
          // 先让 DropdownMenu 关闭，再打开 Dialog，避免两个焦点陷阱同时激活导致栈溢出
          window.setTimeout(() => setIsOpen(true), 50)
        }}
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
