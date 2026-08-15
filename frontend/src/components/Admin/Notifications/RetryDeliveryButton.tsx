import { useMutation, useQueryClient } from "@tanstack/react-query"
import { RotateCcw } from "lucide-react"

import { NotificationsService } from "@/client"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export function RetryDeliveryButton({ deliveryId }: { deliveryId: string }) {
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () => NotificationsService.retryAdminDelivery({ deliveryId }),
    onSuccess: () => {
      showSuccessToast("投递已重新入队发送")
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-notifications"] })
    },
  })

  return (
    <DropdownMenuItem
      disabled={mutation.isPending}
      onClick={() => mutation.mutate()}
    >
      <RotateCcw />
      重试
    </DropdownMenuItem>
  )
}
