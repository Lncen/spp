import { Plus } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import ProductFormDialog from "./ProductForm"

const AddProduct = () => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      <Button className="my-4" onClick={() => setIsOpen(true)}>
        <Plus className="mr-2" />
        添加商品
      </Button>
      <ProductFormDialog isOpen={isOpen} onOpenChange={setIsOpen} />
    </>
  )
}

export default AddProduct
