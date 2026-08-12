import type { AutomationEventStatus } from "@/client"

export const EVENT_STATUS_LABELS: Record<AutomationEventStatus, string> = {
  pending: "待分发",
  dispatching: "分发中",
  dispatched: "已分发",
  failed: "分发失败",
}

export const EVENT_STATUS_BADGE_VARIANT: Record<
  AutomationEventStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  pending: "secondary",
  dispatching: "default",
  dispatched: "outline",
  failed: "destructive",
}
