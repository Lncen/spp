import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowRight, Check, Copy, RefreshCw } from "lucide-react"
import { Fragment, type ReactNode } from "react"

import { OrdersService } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { ORDER_STATUS_BADGE_VARIANT, orderStatusLabel } from "./constants"

const REDEEM_TYPE_LABELS: Record<number, string> = {
  1: "自动履约",
  2: "手动履约",
  3: "API 履约",
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  CNY: "¥",
  USD: "$",
  EUR: "€",
}

function formatDateTime(value?: string | null): string {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { hour12: false })
}

function formatTime(value?: string | null): string {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleTimeString("zh-CN", { hour12: false })
}

function formatAmount(value: string | number): string {
  const text = String(value)
  return text.includes(".") ? text.replace(/\.?0+$/, "") : text
}

function multiplyAmount(value: string | number, factor: number): string {
  const text = String(value)
  const [intPart, fracPart = ""] = text.split(".")
  const scaled = BigInt(`${intPart}${fracPart}`) * BigInt(factor)
  if (!fracPart) return scaled.toString()
  const digits = scaled.toString().padStart(fracPart.length + 1, "0")
  const point = digits.length - fracPart.length
  return `${digits.slice(0, point)}.${digits.slice(point)}`
}

function currencySymbol(currency: string): string {
  return CURRENCY_SYMBOLS[currency] ?? currency
}

function formatPrice(value: string | number, currency: string): string {
  return `${currencySymbol(currency)}${formatAmount(value)}`
}

function CopyButton({ text }: { text: string }) {
  const [copiedText, copy] = useCopyToClipboard()
  const isCopied = copiedText === text

  return (
    <Button
      variant="ghost"
      size="sm"
      className="h-7 gap-1 px-2 text-xs"
      onClick={() => copy(text)}
    >
      {isCopied ? (
        <Check className="size-3 text-green-500" />
      ) : (
        <Copy className="size-3" />
      )}
      {isCopied ? "已复制" : "复制"}
    </Button>
  )
}

function ProductId({ id }: { id: string | null }) {
  const [copiedText, copy] = useCopyToClipboard()

  if (!id) {
    return (
      <span className="text-sm text-muted-foreground inline-block w-10 text-center">
        -
      </span>
    )
  }

  const isCopied = copiedText === id
  const shortId = id.length > 10 ? `${id.slice(0, 8)}...` : id

  return (
    <div className="group flex items-center gap-1.5">
      <span className="font-mono text-xs text-muted-foreground">
        本地商品 ID: {shortId}
      </span>
      <Button
        variant="ghost"
        size="icon"
        className="size-5 transition-opacity group-hover:opacity-100"
        onClick={() => copy(id)}
      >
        {isCopied ? (
          <Check className="size-3 text-green-500" />
        ) : (
          <Copy className="size-3" />
        )}
        <span className="sr-only">复制商品 ID</span>
      </Button>
    </div>
  )
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

function SectionTitle({ children }: { children: ReactNode }) {
  return <h3 className="text-sm font-semibold">{children}</h3>
}

function OrderParams({ params }: { params: Record<string, unknown> }) {
  const entries = Object.entries(params)
  if (entries.length === 0) {
    return <span className="text-sm text-muted-foreground">无</span>
  }
  return (
    <div className="flex flex-col gap-3">
      {entries.map(([key, value]) => {
        const text = String(value)
        return (
          <div key={key} className="flex flex-col gap-1">
            <span className="text-sm text-muted-foreground">{key}</span>
            <div className="flex items-center justify-between gap-3">
              <span className="min-w-0 break-all font-medium">{text}</span>
              <CopyButton text={text} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

interface StatusStep {
  label: string
  time?: string | null
}

function StatusTimeline({ steps }: { steps: StatusStep[] }) {
  return (
    <div className="flex items-start justify-between gap-2">
      {steps.map((step, index) => (
        <Fragment key={step.label}>
          {index > 0 && (
            <ArrowRight className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
          )}
          <div className="flex min-w-0 flex-1 flex-col items-center gap-1">
            <span className="text-sm font-medium">{step.label}</span>
            <span className="font-mono text-xs text-muted-foreground">
              {formatTime(step.time)}
            </span>
          </div>
        </Fragment>
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
  const { data: order, isLoading } = useQuery({
    queryKey: ["orders", "detail", orderId],
    queryFn: () => OrdersService.readOrder({ orderId }),
    enabled: open,
  })
  const queryClient = useQueryClient()
  const { showErrorToast } = useCustomToast()

  const syncMutation = useMutation({
    mutationFn: () => OrdersService.syncOrderStatusApi({ orderId }),
    onSuccess: (updatedOrder) => {
      queryClient.setQueryData(["orders", "detail", orderId], updatedOrder)
      queryClient.invalidateQueries({ queryKey: ["orders"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <div className="flex items-center justify-between gap-4 pr-8">
            <DialogTitle>订单详情</DialogTitle>
            <div className="flex items-center gap-2">
              <LoadingButton
                variant="ghost"
                size="icon"
                className="size-8"
                aria-label="刷新订单"
                loading={syncMutation.isPending}
                onClick={() => syncMutation.mutate()}
              >
                {!syncMutation.isPending && <RefreshCw className="size-4" />}
              </LoadingButton>
              {order && (
                <Badge
                  variant={
                    ORDER_STATUS_BADGE_VARIANT[order.status] ?? "secondary"
                  }
                >
                  {orderStatusLabel(order.status)}
                </Badge>
              )}
            </div>
          </div>
          {order && (
            <div className="flex items-center justify-between gap-4">
              <span className="font-mono text-sm">{order.order_no}</span>
              <CopyButton text={order.order_no} />
            </div>
          )}
        </DialogHeader>
        <div className="flex max-h-[70vh] flex-col gap-6 overflow-y-auto pr-1">
          {isLoading || !order ? (
            <div className="flex flex-col gap-4">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-32 w-full" />
              <Skeleton className="h-28 w-full" />
            </div>
          ) : (
            <>
              <section className="flex flex-col gap-3">
                <SectionTitle>订单状态</SectionTitle>
                <div className="flex flex-col gap-4 rounded-lg border bg-muted/40 p-4">
                  <div className="flex items-center gap-2">
                    <span className="size-2 rounded-full bg-primary" />
                    <span className="text-base font-semibold">
                      {orderStatusLabel(order.status)}
                    </span>
                  </div>
                  <StatusTimeline
                    steps={[
                      { label: "支付", time: order.paid_at },
                      {
                        label: order.canceled_at ? "已取消" : "处理中",
                        time: order.canceled_at || order.processing_at,
                      },
                      {
                        label: order.refunded_at ? "已退款" : "已完成",
                        time: order.refunded_at || order.completed_at,
                      },
                    ]}
                  />
                </div>
              </section>

              <section className="flex flex-col gap-3">
                <SectionTitle>订单</SectionTitle>
                <Card>
                  <CardContent className="flex flex-col gap-2 ">
                    <div className="flex items-start justify-between gap-4">
                      <span className="min-w-0 break-all font-medium">
                        {order.product_name}
                      </span>
                      <span className="shrink-0 text-muted-foreground">
                        × {order.quantity}
                      </span>
                    </div>
                    <ProductId id={order.product_id} />
                    <div className="mt-2 flex flex-col">
                      <DetailRow label="初始数量">
                        {order.start_quantity}
                      </DetailRow>
                      <DetailRow label="当前数量">
                        {order.current_quantity}
                      </DetailRow>
                      <DetailRow label="单价">
                        {formatPrice(order.unit_price, order.currency)}
                      </DetailRow>
                      <DetailRow label="小计">
                        {formatPrice(order.subtotal, order.currency)}
                      </DetailRow>
                      <DetailRow label="履约方式">
                        {REDEEM_TYPE_LABELS[order.fulfillment_type] ??
                          order.fulfillment_type}
                      </DetailRow>
                      <DetailRow label="备注">
                        {order.remark || "-"}
                      </DetailRow>
                    </div>
                  </CardContent>
                </Card>
              </section>
              <section className="flex flex-col gap-3">
                <SectionTitle>售后</SectionTitle>
                {Number(order.refunded_amount) !== 0 && (
                  <Card>
                    <CardContent>
                      退款：{Number(order.refunded_amount)}
                    </CardContent>
                  </Card>
                )}
              </section>
              <section className="flex flex-col gap-3">
                <SectionTitle>下单参数</SectionTitle>
                <Card>
                  <CardContent>
                    <OrderParams params={order.params} />
                  </CardContent>
                </Card>
              </section>

              <section className="flex flex-col gap-3">
                <SectionTitle>金额信息</SectionTitle>
                <Card>
                  <CardContent>
                    <div className="grid grid-cols-3 divide-x">
                      <div className="flex flex-col items-center gap-1 px-2">
                        <span className="text-sm text-muted-foreground">
                          成交金额
                        </span>
                        <span className="text-lg font-semibold">
                          {formatAmount(order.subtotal)}
                        </span>
                      </div>
                      <div className="flex flex-col items-center gap-1 px-2">
                        <span className="text-sm text-muted-foreground">
                          成本价
                        </span>
                        <span className="text-lg font-semibold">
                          {formatAmount(
                            multiplyAmount(order.cost_price, order.quantity),
                          )}
                        </span>
                      </div>
                      <div className="flex flex-col items-center gap-1 px-2">
                        <span className="text-sm text-muted-foreground">
                          损耗
                        </span>
                        <span className="text-lg font-semibold">
                          {formatAmount(order.loss_price)}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </section>

              <section className="flex flex-col gap-3">
                <SectionTitle>履约信息</SectionTitle>
                <div className="flex flex-col">
                  <DetailRow label="上游订单号">
                    {order.supplier_order_id || "-"}
                  </DetailRow>
                  <DetailRow label="供应商">
                    {order.supplier_id || "-"}
                  </DetailRow>
                  <DetailRow label="SKU">{order.sku_id || "-"}</DetailRow>
                  <DetailRow label="履约失败次数">
                    {order.fulfill_failed_count ?? 0}
                  </DetailRow>
                  <DetailRow label="备注">{order.remark || "-"}</DetailRow>
                </div>
              </section>

              <section className="flex flex-col gap-3">
                <SectionTitle>时间信息</SectionTitle>
                <div className="flex flex-col">
                  <DetailRow label="创建时间">
                    {formatDateTime(order.created_at)}
                  </DetailRow>
                  <DetailRow label="支付时间">
                    {formatDateTime(order.paid_at)}
                  </DetailRow>
                  <DetailRow label="开始处理">
                    {formatDateTime(order.processing_at)}
                  </DetailRow>
                  <DetailRow label="完成时间">
                    {formatDateTime(order.completed_at)}
                  </DetailRow>
                </div>
              </section>

              <section className="flex flex-col gap-3">
                <SectionTitle>用户信息</SectionTitle>
                <div className="flex flex-col">
                  <DetailRow label="用户">{order.username || "-"}</DetailRow>
                  <DetailRow label="用户 ID">{order.user_id}</DetailRow>
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
