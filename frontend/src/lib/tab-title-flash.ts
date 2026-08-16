/**
 * 任务栏标签闪烁：收到新消息时在「【新消息】原标题」与原标题之间切换。
 * 页面不在前台时持续闪烁直到用户切回；页面在前台时短暂闪烁几次作为提示。
 */

const FLASH_INTERVAL_MS = 1000
const FLASH_PREFIX = "【新消息】"
const FOCUSED_TOGGLE_COUNT = 4

let originalTitle: string | null = null
let showPrefix = true
let flashTimer: ReturnType<typeof setInterval> | null = null
let remainingToggles = 0

function stopFlash(): void {
  if (flashTimer !== null) {
    clearInterval(flashTimer)
    flashTimer = null
  }
  if (originalTitle !== null) {
    document.title = originalTitle
    originalTitle = null
  }
  window.removeEventListener("focus", stopFlash)
  document.removeEventListener("visibilitychange", handleVisibilityChange)
}

function handleVisibilityChange(): void {
  if (!document.hidden) {
    stopFlash()
  }
}

export function flashTabTitle(): void {
  if (typeof document === "undefined" || flashTimer !== null) {
    return
  }
  originalTitle = document.title
  showPrefix = true
  const focused = document.hasFocus()
  remainingToggles = focused ? FOCUSED_TOGGLE_COUNT : Number.POSITIVE_INFINITY
  document.title = `${FLASH_PREFIX}${originalTitle}`
  flashTimer = setInterval(() => {
    if (originalTitle === null) {
      return
    }
    showPrefix = !showPrefix
    document.title = showPrefix
      ? `${FLASH_PREFIX}${originalTitle}`
      : originalTitle
    if (remainingToggles !== Number.POSITIVE_INFINITY) {
      remainingToggles -= 1
      if (remainingToggles <= 0) {
        stopFlash()
      }
    }
  }, FLASH_INTERVAL_MS)

  if (!focused) {
    window.addEventListener("focus", stopFlash)
    document.addEventListener("visibilitychange", handleVisibilityChange)
  }
}
