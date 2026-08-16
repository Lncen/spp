import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useForm } from "react-hook-form"

import {
  type BackupPublic,
  BackupsService,
  type EntityRestoreStats,
  type RestoreResultPublic,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

interface RestoreBackupDialogProps {
  backup: BackupPublic | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: () => void
}

function statsText(label: string, stats: EntityRestoreStats) {
  return `${label}：新增 ${stats.inserted ?? 0}，更新 ${stats.updated ?? 0}`
}

export function RestoreBackupDialog({
  backup,
  open,
  onOpenChange,
  onSuccess,
}: RestoreBackupDialogProps) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { handleSubmit } = useForm()

  const mutation = useMutation({
    mutationFn: () =>
      BackupsService.restoreBackup({ filename: backup?.filename ?? "" }),
    onSuccess: (result: RestoreResultPublic) => {
      const lines = [
        statsText("用户", result.users),
        statsText("钱包", result.wallets),
        statsText("订单", result.orders),
        statsText("订单参数", result.order_params),
        statsText("供应商", result.suppliers),
      ]
      showSuccessToast(lines.join("；"))
      onOpenChange(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["backups"] })
    },
  })

  const onSubmit = () => {
    if (backup) mutation.mutate()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>恢复备份</DialogTitle>
            <DialogDescription>
              将把备份中的用户、钱包、订单、供应商数据合并回当前系统。
              已存在的数据会被备份内容更新，当前系统中不在备份内的数据不会被删除。
            </DialogDescription>
          </DialogHeader>
          <div className="mt-4 rounded-md bg-muted/40 p-3 text-sm text-muted-foreground">
            备份文件：{backup?.filename}
          </div>
          <DialogFooter className="mt-4">
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>
                取消
              </Button>
            </DialogClose>
            <LoadingButton type="submit" loading={mutation.isPending}>
              开始恢复
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
