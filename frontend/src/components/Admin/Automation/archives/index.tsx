import { useSuspenseQuery } from "@tanstack/react-query"
import type { PaginationState } from "@tanstack/react-table"
import { Suspense, useState } from "react"

import type { AutomationTaskStatus } from "@/client"
import { AutomationService } from "@/client"
import { TASK_STATUS_LABELS } from "@/components/Admin/Automation/tasks/constants"
import Pending from "@/components/Admin/Pending/PendingItems"
import { DataTable } from "@/components/Common/DataTable"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { archiveColumns } from "./columns"

function getArchivesQueryOptions(
  status: AutomationTaskStatus | "all",
  pagination: PaginationState,
) {
  return {
    queryFn: () =>
      AutomationService.readAutomationTaskArchives({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
        status: status === "all" ? undefined : status,
      }),
    queryKey: ["automation-archives", status, pagination],
  }
}

function ArchivesTableContent({
  status,
  pagination,
  setPagination,
}: {
  status: AutomationTaskStatus | "all"
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
}) {
  const { data: archives } = useSuspenseQuery(
    getArchivesQueryOptions(status, pagination),
  )
  return (
    <DataTable
      columns={archiveColumns}
      data={archives.data}
      total={archives.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function ArchivesTable({
  status,
  pagination,
  setPagination,
}: {
  status: AutomationTaskStatus | "all"
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
}) {
  return (
    <Suspense fallback={<Pending />}>
      <ArchivesTableContent
        status={status}
        pagination={pagination}
        setPagination={setPagination}
      />
    </Suspense>
  )
}

export function ArchivesSection() {
  const [status, setStatus] = useState<AutomationTaskStatus | "all">("all")
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })

  const handleStatusChange = (value: string) => {
    setStatus(value as AutomationTaskStatus | "all")
    setPagination((current) => ({ ...current, pageIndex: 0 }))
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">任务归档</h2>
          <p className="text-sm text-muted-foreground">
            终态任务归档记录，按保留期自动清理；失败任务可重新入队。
          </p>
        </div>
        <Select value={status} onValueChange={handleStatusChange}>
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
            {Object.entries(TASK_STATUS_LABELS).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <ArchivesTable
        status={status}
        pagination={pagination}
        setPagination={setPagination}
      />
    </div>
  )
}
