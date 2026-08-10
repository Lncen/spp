import { useMutation, useQueryClient } from "@tanstack/react-query"
import { EllipsisVertical, Eye, XCircle } from "lucide-react"
import { useState } from "react"

import type { OrderListItem, OrderStatus } from "@/client"
import { OrdersService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import OrderDetailDialog from "./OrderDetailDialog"

const CANCELABLE_STATUSES: OrderStatus[] = [1, 2, 3]

interface OrderActionsMenuProps {
  order: OrderListItem
}

export const OrderActionsMenu = ({ order }: OrderActionsMenuProps) => {
  const [menuOpen, setMenuOpen] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)
  const [cancelOpen, setCancelOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const cancelMutation = useMutation({
    mutationFn: () => OrdersService.cancelOrderApi({ orderId: order.id }),
    onSuccess: () => {
      showSuccessToast(`订单 ${order.product_name} 已提交售后申请`)
      setCancelOpen(false)
      setMenuOpen(false)
      queryClient.invalidateQueries({ queryKey: ["orders"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const canCancel = CANCELABLE_STATUSES.includes(order.status)

  return (
    <>
      <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="订单操作">
            <EllipsisVertical />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onSelect={(event) => event.preventDefault()}
            onClick={() => setDetailOpen(true)}
          >
            <Eye />
            查看详情
          </DropdownMenuItem>
          <DropdownMenuItem
            variant="destructive"
            disabled={!canCancel}
            onSelect={(event) => event.preventDefault()}
            onClick={() => setCancelOpen(true)}
          >
            <XCircle />
            取消订单（申请售后）
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <OrderDetailDialog
        orderId={order.id}
        open={detailOpen}
        onOpenChange={setDetailOpen}
      />

      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>取消订单（申请售后）</DialogTitle>
            <DialogDescription>
              {order.product_name} × {order.quantity}
              ，提交后订单状态将变为申请售后中
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="mt-4">
            <DialogClose asChild>
              <Button variant="outline" disabled={cancelMutation.isPending}>
                取消
              </Button>
            </DialogClose>
            <LoadingButton
              variant="destructive"
              loading={cancelMutation.isPending}
              onClick={() => cancelMutation.mutate()}
            >
              确认提交
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default OrderActionsMenu
