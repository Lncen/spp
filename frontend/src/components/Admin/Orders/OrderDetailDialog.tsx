import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import type { ReactNode } from "react"

import type { OrderStatus } from "@/client"
import { OrdersService } from "@/client"
import { Badge } from "@/components/ui/badge"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import {
  ORDER_STATUS_BADGE_VARIANT,
  orderStatusLabel,
} from "./constants"

const STATUS_UPDATE_OPTIONS: OrderStatus[] = [3, 5, 6, 9]
const REFUNDABLE_STATUSES: OrderStatus[] = [3, 5, 6, 10]
const REDEEM_TYPE_LABELS: Record<number, string> = {
  1: "自动发货",
  2: "手动发货",
  3: "API 履约",
}

function formatDateTime(value?: string | null): string {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { hour12: false })
}

function formatAmount(value: string | number): string {
  return Number(value).toFixed(2)
}

function refundAmountError(
  amount: string,
  totalAmount: string,
): string | null {
  const trimmed = amount.trim()
  if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) {
    return "退款金额必须大于 0，最多保留两位小数"
  }
  if (Number(trimmed) > Number(totalAmount)) {
    return "退款金额不能超过订单金额"
  }
  return null
}

interface DetailRowProps {
  label: string
  children: ReactNode
}

function DetailRow({ label, children }: DetailRowProps) {
  return (
    <div className="flex items-start justify-between gap-4 py-1">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="min-w-0 break-all text-right font-medium">
        {children}
      </span>
    </div>
  )
}

function OrderParams({ params }: { params: Record<string, unknown> }) {
  const entries = Object.entries(params)
  if (entries.length === 0) {
    return <span className="text-sm text-muted-foreground">无</span>
  }
  return (
    <div className="space-y-1">
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-start justify-between gap-4 py-1">
          <span className="shrink-0 text-muted-foreground">{key}</span>
          <span className="min-w-0 break-all text-right font-medium">
            {String(value)}
          </span>
        </div>
      ))}
    </div>
  )
}

interface OrderDetailDialogProps {
  orderId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export const OrderDetailDialog = ({
  orderId,
  open,
  onOpenChange,
}: OrderDetailDialogProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [selectedStatus, setSelectedStatus] = useState<OrderStatus>(3)
  const [refundAmount, setRefundAmount] = useState("")
  const [refundError, setRefundError] = useState("")

  const { data: order, isLoading } = useQuery({
    queryKey: ["orders", "detail", orderId],
    queryFn: () => OrdersService.readOrder({ orderId }),
    enabled: open,
  })

  useEffect(() => {
    if (open) {
      setRefundAmount("")
      setRefundError("")
    }
  }, [open])

  useEffect(() => {
    if (open && order) {
      setSelectedStatus(
        STATUS_UPDATE_OPTIONS.includes(order.status)
          ? order.status
          : STATUS_UPDATE_OPTIONS[0],
      )
    }
  }, [open, order])

  const invalidateOrder = () => {
    queryClient.invalidateQueries({ queryKey: ["orders"] })
    queryClient.invalidateQueries({
      queryKey: ["orders", "detail", orderId],
    })
  }

  const statusMutation = useMutation({
    mutationFn: (status: OrderStatus) =>
      OrdersService.updateOrderStatusApi({
        orderId,
        requestBody: { status },
      }),
    onSuccess: (data) => {
      showSuccessToast(`订单状态已更新为 ${orderStatusLabel(data.status)}`)
      invalidateOrder()
    },
    onError: handleError.bind(showErrorToast),
  })

  const refundMutation = useMutation({
    mutationFn: (amount: string) =>
      OrdersService.refundOrderApi({
        orderId,
        requestBody: { amount },
      }),
    onSuccess: (data) => {
      showSuccessToast(
        `退款成功，订单状态已更新为 ${orderStatusLabel(data.status)}`,
      )
      setRefundAmount("")
      invalidateOrder()
    },
    onError: handleError.bind(showErrorToast),
  })

  const handleOpenChange = (nextOpen: boolean) => {
    onOpenChange(nextOpen)
    if (!nextOpen) {
      setRefundAmount("")
      setRefundError("")
    }
  }

  const submitStatus = () => {
    statusMutation.mutate(selectedStatus)
  }

  const canRefund =
    order != null && REFUNDABLE_STATUSES.includes(order.status)

  const submitRefund = () => {
    if (!order) return
    const error = refundAmountError(refundAmount, order.total_amount)
    if (error) {
      setRefundError(error)
      return
    }
    refundMutation.mutate(refundAmount.trim())
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>订单详情</DialogTitle>
          <DialogDescription>
            {order ? `订单号：${order.order_no}` : "加载订单信息"}
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-[70vh] space-y-5 overflow-y-auto pr-1 [scrollbar-width:thin] [scrollbar-color:var(--border)_transparent] [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar]:h-2 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border">
          {isLoading || !order ? (
            <div className="space-y-4">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-32 w-full" />
              <Skeleton className="h-28 w-full" />
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Badge
                  variant={
                    ORDER_STATUS_BADGE_VARIANT[order.status] ?? "secondary"
                  }
                >
                  {orderStatusLabel(order.status)}
                </Badge>
                {!order.can_refund && (
                  <Badge variant="outline">用户不可申请退款</Badge>
                )}
              </div>
              <section className="grid gap-x-6 sm:grid-cols-2">
                <DetailRow label="用户">{order.username || "-"}</DetailRow>
                <DetailRow label="商品">{order.product_name}</DetailRow>
                <DetailRow label="数量">{order.quantity}</DetailRow>
                <DetailRow label="单价">
                  {formatAmount(order.unit_price)} {order.currency}
                </DetailRow>
                <DetailRow label="小计">
                  {formatAmount(order.subtotal)}
                </DetailRow>
                <DetailRow label="订单金额">
                  {formatAmount(order.total_amount)}
                </DetailRow>
                <DetailRow label="履约方式">
                  {REDEEM_TYPE_LABELS[order.fulfillment_type] ??
                    order.fulfillment_type}
                </DetailRow>
                <DetailRow label="供应商订单号">
                  {order.supplier_order_id || "-"}
                </DetailRow>
                <DetailRow label="备注">{order.remark || "-"}</DetailRow>
                <DetailRow label="下单时间">
                  {formatDateTime(order.created_at)}
                </DetailRow>
                <DetailRow label="支付时间">
                  {formatDateTime(order.paid_at)}
                </DetailRow>
                <DetailRow label="处理时间">
                  {formatDateTime(order.processing_at)}
                </DetailRow>
                <DetailRow label="完成时间">
                  {formatDateTime(order.completed_at)}
                </DetailRow>
                <DetailRow label="取消时间">
                  {formatDateTime(order.canceled_at)}
                </DetailRow>
                <DetailRow label="退款时间">
                  {formatDateTime(order.refunded_at)}
                </DetailRow>
              </section>
              <section className="space-y-1">
                <h3 className="text-sm font-semibold">订单参数</h3>
                <OrderParams params={order.params} />
              </section>
              <section className="space-y-4 rounded-md border p-4">
                <div>
                  <h3 className="text-sm font-semibold">设置订单状态</h3>
                  <p className="text-xs text-muted-foreground">
                    当前状态：{orderStatusLabel(order.status)}
                  </p>
                </div>
                <div className="flex flex-wrap items-end gap-2">
                  <div className="grid min-w-48 flex-1 gap-1.5">
                    <Label htmlFor="order-status-select">目标状态</Label>
                    <Select
                      value={String(selectedStatus)}
                      onValueChange={(value) =>
                        setSelectedStatus(Number(value) as OrderStatus)
                      }
                    >
                      <SelectTrigger
                        id="order-status-select"
                        className="w-full"
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {STATUS_UPDATE_OPTIONS.map((status) => (
                          <SelectItem key={status} value={String(status)}>
                            {orderStatusLabel(status)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <LoadingButton
                    onClick={submitStatus}
                    loading={statusMutation.isPending}
                  >
                    保存状态
                  </LoadingButton>
                </div>
              </section>
              <section className="space-y-4 rounded-md border p-4">
                <div>
                  <h3 className="text-sm font-semibold">手动退款</h3>
                  <p className="text-xs text-muted-foreground">
                    订单金额 {formatAmount(order.total_amount)}
                  </p>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="refund-amount">退款金额</Label>
                  <div className="flex gap-2">
                    <Input
                      id="refund-amount"
                      type="number"
                      min="0.01"
                      step="0.01"
                      placeholder="0.00"
                      value={refundAmount}
                      disabled={!canRefund || refundMutation.isPending}
                      onChange={(event) => {
                        setRefundAmount(event.target.value)
                        setRefundError("")
                      }}
                    />
                    <LoadingButton
                      onClick={submitRefund}
                      loading={refundMutation.isPending}
                      disabled={!canRefund}
                    >
                      确认退款
                    </LoadingButton>
                  </div>
                  {refundError && (
                    <p className="text-sm text-destructive">{refundError}</p>
                  )}
                  {!canRefund && (
                    <p className="text-sm text-muted-foreground">
                      当前状态不可退款
                    </p>
                  )}
                </div>
              </section>
            </>
          )}
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">关闭</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default OrderDetailDialog
