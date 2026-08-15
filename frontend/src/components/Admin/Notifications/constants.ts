import type { NotificationAdminItem } from "@/client"

export const CHANNEL_LABELS: Record<string, string> = {
  in_app: "站内",
  email: "邮件",
}

export const DELIVERY_STATUS_LABELS: Record<string, string> = {
  pending: "待发送",
  sending: "发送中",
  sent: "已发送",
  failed: "失败",
  canceled: "已取消",
}

export const DELIVERY_STATUS_BADGE_VARIANT: Record<
  string,
  | "default"
  | "secondary"
  | "destructive"
  | "outline"
  | "success"
  | "warning"
  | "info"
> = {
  pending: "secondary",
  sending: "info",
  sent: "success",
  failed: "destructive",
  canceled: "outline",
}

export function sourceLabel(item: NotificationAdminItem): string {
  if (item.rule_id) return `规则:${item.rule_id}`
  if (item.event_id) return `事件:${item.event_id.slice(0, 8)}`
  return "手动发送"
}
