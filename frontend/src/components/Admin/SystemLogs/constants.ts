export const LOG_LEVEL_LABELS: Record<string, string> = {
  info: "INFO",
  warning: "WARNING",
  error: "ERROR",
  critical: "CRITICAL",
}

export const LOG_LEVEL_BADGE_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  info: "default",
  warning: "secondary",
  error: "destructive",
  critical: "destructive",
}

export const LOG_STATUS_LABELS: Record<string, string> = {
  success: "成功",
  failed: "失败",
  unknown: "未知",
}

export const LOG_STATUS_BADGE_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  success: "outline",
  failed: "destructive",
  unknown: "secondary",
}
