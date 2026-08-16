import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { SettingsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const BACKUP_DIR_KEY = "backup_dir"

export function BackupDirectorySettings() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [path, setPath] = useState("")

  const { data: settings } = useQuery({
    queryKey: ["settings", BACKUP_DIR_KEY],
    queryFn: SettingsService.readSettings,
  })

  const backupDir =
    settings?.data.find((setting) => setting.key === BACKUP_DIR_KEY)?.value ??
    ""
  const currentPath = typeof backupDir === "string" ? backupDir : ""

  const mutation = useMutation({
    mutationFn: (value: string) =>
      SettingsService.updateSettingEndpoint({
        key: BACKUP_DIR_KEY,
        requestBody: { value },
      }),
    onSuccess: () => {
      showSuccessToast("备份目录已更新")
      queryClient.invalidateQueries({ queryKey: ["settings"] })
      queryClient.invalidateQueries({ queryKey: ["backups"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle>备份保存目录</CardTitle>
        <CardDescription>
          Docker 环境中请填写容器内已挂载的路径；留空时使用环境变量 BACKUP_DIR。
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2">
          <Input
            value={path || currentPath}
            placeholder="例如：/app/backups"
            onChange={(event) => setPath(event.target.value)}
            className="max-w-xl"
          />
          <LoadingButton
            type="button"
            loading={mutation.isPending}
            disabled={path === currentPath}
            onClick={() => mutation.mutate(path)}
          >
            保存
          </LoadingButton>
          {!path && currentPath && (
            <Button
              type="button"
              variant="ghost"
              onClick={() => setPath(currentPath)}
            >
              使用当前值
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
