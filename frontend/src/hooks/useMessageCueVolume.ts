import { useQuery } from "@tanstack/react-query"
import { useEffect } from "react"

import { SettingsService } from "@/client"
import {
  MESSAGE_CUE_VOLUME,
  setMessageCueVolume,
} from "@/lib/new-message-alert"

/** 从全局设置同步新消息提示音音量到提醒模块 */
export function useMessageCueVolume(): void {
  const { data } = useQuery({
    queryKey: ["settings"],
    queryFn: () => SettingsService.readSettings(),
    staleTime: 5 * 60 * 1000,
  })
  const value = data?.data.find(
    (item) => item.key === MESSAGE_CUE_VOLUME,
  )?.value

  useEffect(() => {
    if (typeof value === "number") {
      setMessageCueVolume(value)
    }
  }, [value])
}
