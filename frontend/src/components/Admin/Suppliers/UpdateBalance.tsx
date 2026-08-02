import { useMutation, useQueryClient } from "@tanstack/react-query"
import { RefreshCw } from "lucide-react"

import type { SuppliersPublic } from "@/client"
import { SuppliersService } from "@/client"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

interface UpdateBalanceProps {
  id: string
}

const UpdateBalance = ({ id }: UpdateBalanceProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: () => SuppliersService.readSupplierBalance({ id }),
    onSuccess: (data) => {
      showSuccessToast(`余额已更新为 ${data.balance}`)
      queryClient.setQueryData<SuppliersPublic>(["suppliers"], (old) => {
        if (!old) return old
        return {
          ...old,
          data: old.data.map((supplier) =>
            supplier.id === id
              ? { ...supplier, balance: data.balance }
              : supplier,
          ),
        }
      })
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <DropdownMenuItem
      disabled={mutation.isPending}
      onClick={() => mutation.mutate()}
    >
      <RefreshCw className={cn(mutation.isPending && "animate-spin")} />
      更新余额
    </DropdownMenuItem>
  )
}

export default UpdateBalance
