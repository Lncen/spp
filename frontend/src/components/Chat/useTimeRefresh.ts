import { useEffect, useState } from "react"

/**
 * 相对时间刷新：相对文案（刚刚 / N 分钟前）不会自己变化，
 * 由该 hook 每分钟触发一次重渲染，避免界面长时间停留在旧文案。
 */
export function useTimeRefresh(intervalMs = 60_000): void {
  const [, setTick] = useState(0)

  useEffect(() => {
    const timer = window.setInterval(
      () => setTick((value) => value + 1),
      intervalMs,
    )
    return () => window.clearInterval(timer)
  }, [intervalMs])
}
