import { EllipsisVertical } from "lucide-react"
import { useState } from "react"

import type { SupplierPublic } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import DeleteSupplier from "./DeleteSupplier"
import EditSupplier from "./EditSupplier"
import SyncProducts from "./SyncProducts"
import UpdateBalance from "./UpdateBalance"

interface SupplierActionsMenuProps {
  supplier: SupplierPublic
}

export const SuppliersActionsMenu = ({
  supplier,
}: SupplierActionsMenuProps) => {
  const [open, setOpen] = useState(false)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <EditSupplier supplier={supplier} onSuccess={() => setOpen(false)} />
        <UpdateBalance id={supplier.id} />
        <SyncProducts id={supplier.id} />
        <DeleteSupplier
          id={supplier.id}
          name={supplier.name}
          onSuccess={() => setOpen(false)}
        />
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default SuppliersActionsMenu
