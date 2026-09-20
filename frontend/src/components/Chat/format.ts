/**
 * 聊天时间展示：统一用相对时间
 *
 * 刚刚 / N 分钟前 / N 小时前 / 昨天 / N 天前；超过一周回退到具体日期，
 * 避免久远消息一直显示「N 天前」这种不精确文案。
 * 相对时间需要配合 `useTimeRefresh()` 定时刷新，否则会停在旧文案。
 */
const MINUTE_MS = 60_000
const DAY_MS = 24 * 60 * 60 * 1000
const DAYS_BEFORE_ABSOLUTE = 7

export function formatChatTime(value?: string | null): string {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  if (diff < 0) {
    return formatAbsolute(date, now)
  }
  const minutes = Math.floor(diff / MINUTE_MS)
  if (minutes < 1) return "刚刚"
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = calendarDaysAgo(now, date)
  if (days <= 1) return "昨天"
  if (days < DAYS_BEFORE_ABSOLUTE) return `${days} 天前`
  return formatAbsolute(date, now)
}

/** 自然日差值：跨天即算一天，不受小时数影响 */
function calendarDaysAgo(now: Date, date: Date): number {
  const startOfNow = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())
  const startOfDate = Date.UTC(
    date.getFullYear(),
    date.getMonth(),
    date.getDate(),
  )
  return Math.round((startOfNow - startOfDate) / DAY_MS)
}

function formatAbsolute(date: Date, now: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  if (date.getFullYear() === now.getFullYear()) {
    return `${month}/${day}`
  }
  return `${date.getFullYear()}/${month}/${day}`
}
