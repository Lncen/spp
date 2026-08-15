import { Pencil } from "lucide-react"
import { useState } from "react"

import type { ProductCategoryPublic } from "@/client"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import ProductCategoryFormDialog from "./ProductCategoryForm"

interface EditProductCategoryProps {
  category: ProductCategoryPublic
  onSuccess: () => void
}

const EditProductCategory = ({
  category,
  onSuccess,
}: EditProductCategoryProps) => {
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
        编辑分类
      </DropdownMenuItem>
      <ProductCategoryFormDialog
        category={category}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
        onSuccess={onSuccess}
      />
    </>
  )
}

export default EditProductCategory
