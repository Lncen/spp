import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { AlertTriangle, Check, Copy } from "lucide-react"
import { type ReactNode, useEffect, useState } from "react"

import type { OrderStatus } from "@/client"
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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"
import { ORDER_STATUS_BADGE_VARIANT, orderStatusLabel } from "./constants"

type AfterSaleType = "cancel" | "refund" | "refulfill"

const AFTER_SALE_TYPE_OPTIONS: {
  value: AfterSaleType
  label: string
  description: string
}[] = [
  {
    value: "cancel",
    label: "退单",
    description: "取消订单并全额退款",
  },
  {
    value: "refund",
    label: "退款",
    description: "按填写金额退款到用户余额",
  },
  {
    value: "refulfill",
    label: "补发 / 重新履约",
    description: "重新触发上游履约流程",
  },
]

const AFTER_SALE_REASONS = [
  "质量原因",
  "数量不符",
  "重复下单",
  "订单错误",
  "其他",
] as const

// 退单可选状态：已支付/待处理/处理中/异常
const CANCELABLE_STATUSES: OrderStatus[] = [1, 2, 3, 9]
const REFUNDABLE_STATUS: OrderStatus = 6
const REFULFILLABLE_STATUS: OrderStatus = 9

const AMOUNT_PATTERN = /^\d+(\.\d{1,7})?$/

function isTypeAvailable(
  type: AfterSaleType,
  status: OrderStatus | undefined,
): boolean {
  if (status === undefined) return false
  if (type === "cancel") return CANCELABLE_STATUSES.includes(status)
  if (type === "refund") return status === REFUNDABLE_STATUS
  return status === REFULFILLABLE_STATUS
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

function DetailRow({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
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

interface AfterSaleDialogProps {
  orderId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

export const AfterSaleDialog = ({
  orderId,
  open,
  onOpenChange,
}: AfterSaleDialogProps) => {
  const { data: order, isLoading } = useQuery({
    queryKey: ["orders", "detail", orderId],
    queryFn: () => OrdersService.readOrder({ orderId }),
    enabled: open,
  })
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const [type, setType] = useState<AfterSaleType | undefined>(undefined)
  const [amount, setAmount] = useState("")
  const [reason, setReason] = useState<string | undefined>(undefined)
  const [remark, setRemark] = useState("")

  useEffect(() => {
    if (!open || !order) return
    const firstAvailable = AFTER_SALE_TYPE_OPTIONS.find((option) =>
      isTypeAvailable(option.value, order.status),
    )?.value
    setType(firstAvailable)
    setAmount(order.total_amount)
    setReason(undefined)
    setRemark("")
  }, [open, order])

  const handleReasonChange = (value: string) => {
    setReason(value)
    setRemark((current) => {
      const trimmed = current.trim()
      if (!trimmed || /^原因：.+$/.test(trimmed)) {
        return `原因：${value}`
      }
      return `${trimmed}\n原因：${value}`
    })
  }

  const amountValid =
    type !== "refund" ||
    (AMOUNT_PATTERN.test(amount) &&
      Number(amount) > 0 &&
      Number(amount) <= Number(order?.total_amount ?? 0))
  const canSubmit = type !== undefined && amountValid

  const submitMutation = useMutation({
    mutationFn: async () => {
      if (!order || !type) return
      const note = remark.trim() || undefined
      if (type === "cancel") {
        return OrdersService.cancelOrderApi({
          orderId: order.id,
          requestBody: { remark: note },
        })
      }
      if (type === "refund") {
        return OrdersService.refundOrderApi({
          orderId: order.id,
          requestBody: { amount, remark: note },
        })
      }
      return OrdersService.fulfillOrderApi({
        orderId: order.id,
        requestBody: { remark: note },
      })
    },
    onSuccess: () => {
      showSuccessToast(`订单 ${order?.product_name ?? ""} 售后处理成功`)
      onOpenChange(false)
      queryClient.invalidateQueries({ queryKey: ["orders"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>售后处理</DialogTitle>
        </DialogHeader>
        <div className="flex max-h-[70vh] flex-col gap-5 overflow-y-auto pr-1">
          {isLoading || !order ? (
            <div className="flex flex-col gap-4">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : (
            <>
              <section className="flex flex-col gap-3">
                <SectionTitle>
                  <span className="flex items-center gap-1 text-sm">
                    <span className="font-mono">订单号：{order.order_no}</span>
                    <CopyButton text={order.order_no} />
                  </span>
                </SectionTitle>
                <Card>
                  <CardContent className="flex flex-col">
                    <DetailRow label="用户">{order.username || "-"}</DetailRow>
                    <DetailRow label="参数">
                      {order.params && Object.keys(order.params).length > 0 ? (
                        <div className="flex flex-col gap-2 w-full">
                          {Object.entries(order.params).map(([key, value]) => (
                            <div key={key} className="flex items-center gap-2">
                              <span className="font-medium text-gray-600">
                                {key}:
                              </span>
                              {typeof value === "string" &&
                              value.startsWith("http") ? (
                                <>
                                  <a
                                    href={value}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-blue-500 underline flex-1 truncate"
                                  >
                                    {value}
                                  </a>
                                  <CopyButton text={value} />
                                </>
                              ) : (
                                <>
                                  <span className="flex-1">
                                    {String(value)}
                                  </span>
                                  <CopyButton text={String(value)} />
                                </>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        "-"
                      )}
                    </DetailRow>
                    <DetailRow label="供应商">
                      {order.supplier_name || "-"}
                    </DetailRow>
                    <DetailRow label="上游单号">
                      <span className="flex-1">
                          {String(order.supplier_order_id) || "-"}
                      </span>
                      <CopyButton text={String(order.supplier_order_id)} />
                    </DetailRow>
                    <DetailRow label="商品">{order.product_name}</DetailRow>
                    <DetailRow label="数量">× {order.quantity}</DetailRow>
                    <DetailRow label="金额">{order.total_amount}</DetailRow>

                    <DetailRow label="订单状态">
                      <Badge
                        variant={
                          ORDER_STATUS_BADGE_VARIANT[order.status] ??
                          "secondary"
                        }
                      >
                        {orderStatusLabel(order.status)}
                      </Badge>
                    </DetailRow>
                    <DetailRow label="备注">{order.remark || "-"}</DetailRow>
                  </CardContent>
                </Card>
              </section>

              <section className="flex flex-col gap-3">
                <SectionTitle>售后类型</SectionTitle>
                <RadioGroup
                  value={type}
                  onValueChange={(value) => setType(value as AfterSaleType)}
                  className="grid gap-2"
                >
                  {AFTER_SALE_TYPE_OPTIONS.map((option) => {
                    const available = isTypeAvailable(
                      option.value,
                      order.status,
                    )
                    return (
                      <div
                        key={option.value}
                        className={cn(
                          "flex items-start gap-3 rounded-md border px-3 py-2.5",
                          available && "hover:bg-muted/50",
                          !available && "cursor-not-allowed opacity-50",
                          type === option.value && "border-primary",
                        )}
                      >
                        <RadioGroupItem
                          value={option.value}
                          id={`after-sale-${option.value}`}
                          disabled={!available}
                          className="mt-0.5"
                        />
                        <div className="flex flex-col gap-0.5">
                          <Label
                            htmlFor={`after-sale-${option.value}`}
                            className={cn(
                              "cursor-pointer",
                              !available && "cursor-not-allowed",
                            )}
                          >
                            {option.label}
                          </Label>
                          <span className="text-xs text-muted-foreground">
                            {option.description}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </RadioGroup>
              </section>

              {type === "refund" && (
                <section className="flex flex-col gap-3">
                  <SectionTitle>退款金额</SectionTitle>
                  <div className="flex flex-col gap-2">
                    <Input
                      value={amount}
                      onChange={(event) => setAmount(event.target.value)}
                      inputMode="decimal"
                      placeholder="0.0000000"
                      aria-invalid={!amountValid}
                    />
                    <p className="text-sm text-muted-foreground">
                      可退款金额：{order.total_amount}
                    </p>
                  </div>
                </section>
              )}

              <section className="flex flex-col gap-3">
                <SectionTitle>售后原因</SectionTitle>
                <Select value={reason} onValueChange={handleReasonChange}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="请选择售后原因" />
                  </SelectTrigger>
                  <SelectContent>
                    {AFTER_SALE_REASONS.map((item) => (
                      <SelectItem key={item} value={item}>
                        {item}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </section>

              <section className="flex flex-col gap-3">
                <SectionTitle>处理备注</SectionTitle>
                <Textarea
                  value={remark}
                  onChange={(event) => setRemark(event.target.value)}
                  placeholder="填写处理备注，选择售后原因后将自动填入"
                />
              </section>

              {(type === "cancel" || type === "refund") && (
                <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                  <span>此操作将直接退还用户余额，操作后不可撤销。</span>
                </div>
              )}
            </>
          )}
        </div>
        <DialogFooter className="mt-4">
          <DialogClose asChild>
            <Button variant="outline" disabled={submitMutation.isPending}>
              取消
            </Button>
          </DialogClose>
          <LoadingButton
            loading={submitMutation.isPending}
            disabled={!canSubmit}
            onClick={() => submitMutation.mutate()}
          >
            确认处理
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default AfterSaleDialog
