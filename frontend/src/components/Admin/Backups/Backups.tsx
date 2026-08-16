import {
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query"
import type { PaginationState } from "@tanstack/react-table"
import { Download } from "lucide-react"
import { Suspense, useState } from "react"

import { type BackupPublic, BackupsService, OpenAPI } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { BackupDirectorySettings } from "./BackupDirectorySettings"
import { backupColumns } from "./columns"
import { DeleteBackupDialog } from "./DeleteBackupDialog"
import PendingBackups from "./PendingBackups"
import { RestoreBackupDialog } from "./RestoreBackupDialog"

function getBackupsQueryOptions(pagination: PaginationState) {
  return {
    queryFn: () =>
      BackupsService.readBackups({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
      }),
    queryKey: ["backups", pagination],
  }
}

function BackupsTable({
  pagination,
  setPagination,
  onDownload,
  onRestore,
  onDelete,
}: {
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
  onDownload: (backup: BackupPublic) => void
  onRestore: (backup: BackupPublic) => void
  onDelete: (backup: BackupPublic) => void
}) {
  const { data } = useSuspenseQuery(getBackupsQueryOptions(pagination))

  return (
    <DataTable
      columns={backupColumns({
        onDownload,
        onRestore,
        onDelete,
      })}
      data={data.data}
      total={data.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function BackupsTableSuspended({
  pagination,
  setPagination,
  onDownload,
  onRestore,
  onDelete,
}: {
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
  onDownload: (backup: BackupPublic) => void
  onRestore: (backup: BackupPublic) => void
  onDelete: (backup: BackupPublic) => void
}) {
  return (
    <Suspense fallback={<PendingBackups />}>
      <BackupsTable
        pagination={pagination}
        setPagination={setPagination}
        onDownload={onDownload}
        onRestore={onRestore}
        onDelete={onDelete}
      />
    </Suspense>
  )
}

export function BackupsSection() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const [restoreTarget, setRestoreTarget] = useState<BackupPublic | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<BackupPublic | null>(null)

  const createMutation = useMutation({
    mutationFn: () => BackupsService.createBackup(),
    onSuccess: () => {
      showSuccessToast("备份已创建")
      queryClient.invalidateQueries({ queryKey: ["backups"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const downloadMutation = useMutation({
    mutationFn: async (filename: string) => {
      const token = localStorage.getItem("access_token")
      const response = await fetch(
        `${OpenAPI.BASE}/api/v1/backups/${encodeURIComponent(filename)}/download`,
        {
          headers: { Authorization: `Bearer ${token || ""}` },
        },
      )
      if (!response.ok) {
        throw new Error("下载失败")
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = filename
      link.click()
      URL.revokeObjectURL(url)
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight">数据备份</h2>
          <p className="text-muted-foreground">
            备份用户、钱包、近 48 小时订单与供应商数据，用于数据恢复
          </p>
        </div>
        <LoadingButton
          type="button"
          loading={createMutation.isPending}
          onClick={() => createMutation.mutate()}
        >
          <Download data-icon="inline-start" />
          立即备份
        </LoadingButton>
      </div>

      <BackupDirectorySettings />

      <BackupsTableSuspended
        pagination={pagination}
        setPagination={setPagination}
        onDownload={(backup) => downloadMutation.mutate(backup.filename)}
        onRestore={setRestoreTarget}
        onDelete={setDeleteTarget}
      />

      <RestoreBackupDialog
        backup={restoreTarget}
        open={restoreTarget !== null}
        onOpenChange={(open) => {
          if (!open) setRestoreTarget(null)
        }}
        onSuccess={() => setRestoreTarget(null)}
      />
      <DeleteBackupDialog
        backup={deleteTarget}
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
        onSuccess={() => setDeleteTarget(null)}
      />
    </div>
  )
}
