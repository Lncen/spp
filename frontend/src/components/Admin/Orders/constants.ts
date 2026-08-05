import type { OrderStatus } from "@/client"

export const ORDER_STATUS_OPTIONS: { value: OrderStatus; label: string }[] = [
  { value: 1, label: "已支付" },
  { value: 2, label: "待处理" },
  { value: 3, label: "处理中" },
  { value: 4, label: "补单中" },
  { value: 5, label: "退单中" },
  { value: 6, label: "已完成" },
  { value: 7, label: "已取消" },
  { value: 8, label: "已退款" },
  { value: 9, label: "有异常" },
  { value: 10, label: "申请售后中" },
]

export const ORDER_STATUS_BADGE_VARIANT: Record<
  OrderStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  1: "default",
  2: "secondary",
  3: "outline",
  4: "outline",
  5: "secondary",
  6: "default",
  7: "secondary",
  8: "secondary",
  9: "destructive",
  10: "outline",
}

export function orderStatusLabel(value: OrderStatus): string {
  return (
    ORDER_STATUS_OPTIONS.find((option) => option.value === value)?.label ??
    String(value)
  )
}
