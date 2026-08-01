import { Plus } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import ProductCategoryFormDialog from "./ProductCategoryForm"

const AddProductCategory = () => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      <Button className="my-4" onClick={() => setIsOpen(true)}>
        <Plus className="mr-2" />
        添加分类
      </Button>
      <ProductCategoryFormDialog isOpen={isOpen} onOpenChange={setIsOpen} />
    </>
  )
}

export default AddProductCategory
