import { EllipsisVertical, Eye, Wrench } from "lucide-react"
import { useState } from "react"

import type { OrderListItem } from "@/client"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import AfterSaleDialog from "./AfterSaleDialog"
import OrderDetailDialog from "./OrderDetailDialog"

interface OrderActionsMenuProps {
  order: OrderListItem
}

export const OrderActionsMenu = ({ order }: OrderActionsMenuProps) => {
  const [menuOpen, setMenuOpen] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)
  const [afterSaleOpen, setAfterSaleOpen] = useState(false)

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
            onSelect={() => {
              setMenuOpen(false)
              // 先关闭菜单再打开 Dialog，避免两个焦点陷阱同时激活导致栈溢出
              window.setTimeout(() => setDetailOpen(true), 50)
            }}
          >
            <Eye />
            查看详情
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => {
              setMenuOpen(false)
              // 先关闭菜单再打开 Dialog，避免两个焦点陷阱同时激活导致栈溢出
              window.setTimeout(() => setAfterSaleOpen(true), 50)
            }}
          >
            <Wrench />
            售后处理
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <OrderDetailDialog
        orderId={order.id}
        open={detailOpen}
        onOpenChange={setDetailOpen}
      />

      <AfterSaleDialog
        orderId={order.id}
        open={afterSaleOpen}
        onOpenChange={setAfterSaleOpen}
      />
    </>
  )
}

export default OrderActionsMenu
