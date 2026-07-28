import { useMutation, useQueryClient } from "@tanstack/react-query"
import { EllipsisVertical, RefreshCw } from "lucide-react"
import { useState } from "react"

import type { SupplierPublic } from "@/client"
import { SuppliersService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import DeleteSupplier from "./DeleteSupplier"
import EditSupplier from "./EditSupplier"

interface SupplierActionsMenuProps {
  supplier: SupplierPublic
}

export const SuppliersActionsMenu = ({ supplier }: SupplierActionsMenuProps) => {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const syncMutation = useMutation({
    mutationFn: (id: string) =>
      SuppliersService.syncSupplierBalance({ id }),
    onSuccess: (data) => {
      showSuccessToast(`余额同步成功：${data.balance ?? "无"}`)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["suppliers"] })
    },
  })

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <EllipsisVertical />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          onSelect={(e) => e.preventDefault()}
          onClick={() => syncMutation.mutate(supplier.id)}
          disabled={syncMutation.isPending}
        >
          <RefreshCw className={syncMutation.isPending ? "animate-spin" : ""} />
          同步余额
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <EditSupplier supplier={supplier} onSuccess={() => setOpen(false)} />
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
