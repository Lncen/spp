import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"

import { type SettingRead, SettingsService, type SettingUpdate } from "@/client"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { EditValueDialog } from "./EditValueDialog"

interface SettingRowProps {
  setting: SettingRead
}

export const SettingRow = ({ setting }: SettingRowProps) => {
  const [isEditOpen, setIsEditOpen] = useState(false)
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

  const toggleValue = (checked: boolean) => {
    mutation.mutate({ value: checked })
  }

  return (
    <div className="flex items-center justify-between gap-4 py-4">
      <p className="text-sm">{setting.description || setting.key}</p>
      {typeof setting.value === "boolean" ? (
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
