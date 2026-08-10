import type { AutomationTaskStatus } from "@/client"

export const TASK_STATUS_LABELS: Record<AutomationTaskStatus, string> = {
  pending: "待执行",
  running: "执行中",
  success: "成功",
  failed: "失败",
  canceled: "已取消",
}

export const TASK_STATUS_BADGE_VARIANT: Record<
  AutomationTaskStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  pending: "secondary",
  running: "default",
  success: "outline",
  failed: "destructive",
  canceled: "outline",
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { hour12: false })
}
