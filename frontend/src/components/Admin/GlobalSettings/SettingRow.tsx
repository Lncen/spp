import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useEffect, useState } from "react"

import { type SettingRead, SettingsService, type SettingUpdate } from "@/client"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import useCustomToast from "@/hooks/useCustomToast"
import { MESSAGE_CUE_VOLUME } from "@/lib/new-message-alert"
import { handleError } from "@/utils"
import { EditValueDialog } from "./EditValueDialog"

interface SettingRowProps {
  setting: SettingRead
}

export const SettingRow = ({ setting }: SettingRowProps) => {
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [volume, setVolume] = useState(() =>
    Number.isFinite(Number(setting.value)) ? Number(setting.value) : 0.15,
  )
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: (requestBody: SettingUpdate) =>
      SettingsService.updateSettingEndpoint({
        key: setting.key,
        requestBody,
      }),
    onSuccess: () => {
      showSuccessToast(`「${setting.description || setting.key}」已更新`)
      setIsEditOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] })
    },
  })

  useEffect(() => {
    if (setting.key === MESSAGE_CUE_VOLUME) {
      setVolume(
        Number.isFinite(Number(setting.value)) ? Number(setting.value) : 0.15,
      )
    }
  }, [setting])

  const toggleValue = (checked: boolean) => {
    mutation.mutate({ value: checked })
  }

  const commitVolume = () => {
    const next = Number(volume) || 0
    if (next !== Number(setting.value)) {
      mutation.mutate({ value: next, type: setting.type })
    }
  }

  return (
    <div className="flex items-center justify-between gap-4 py-4">
      <p className="text-sm">{setting.description || setting.key}</p>
      {setting.key === MESSAGE_CUE_VOLUME ? (
        <div className="flex items-center gap-3">
          <input
            type="range"
            min={0}
            max={2}
            step={0.05}
            value={volume}
            disabled={mutation.isPending}
            onChange={(event) => setVolume(Number(event.target.value))}
            onPointerUp={commitVolume}
            onKeyUp={commitVolume}
            className="w-40 accent-primary"
            aria-label={setting.description || setting.key}
          />
          <span className="w-12 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
            {Math.round(volume * 100)}%
          </span>
        </div>
      ) : typeof setting.value === "boolean" ? (
        <Switch
          checked={setting.value}
          onCheckedChange={toggleValue}
          disabled={mutation.isPending}
          aria-label={setting.description || setting.key}
        />
      ) : (
        <Button variant="outline" size="sm" onClick={() => setIsEditOpen(true)}>
          <Pencil data-icon="inline-start" />
          编辑
        </Button>
      )}
      <EditValueDialog
        setting={setting}
        open={isEditOpen}
        isPending={mutation.isPending}
        onOpenChange={setIsEditOpen}
        onSave={(value) => mutation.mutate({ value })}
      />
    </div>
  )
}
