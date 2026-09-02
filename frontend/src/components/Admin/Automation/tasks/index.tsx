import { useSuspenseQuery } from "@tanstack/react-query"
import type { PaginationState } from "@tanstack/react-table"
import { Suspense, useState } from "react"

import type { AutomationTaskStatus } from "@/client"
import { AutomationService } from "@/client"
import Pending from "@/components/Admin/Pending/PendingItems"
import { DataTable } from "@/components/Common/DataTable"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import AddTaskDialog from "./AddTaskDialog"
import { taskColumns } from "./columns"
import { TASK_STATUS_LABELS } from "./constants"

function getTasksQueryOptions(
  status: AutomationTaskStatus | "all",
  pagination: PaginationState,
) {
  return {
    queryFn: () =>
      AutomationService.readAutomationTasks({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
        status: status === "all" ? undefined : status,
      }),
    queryKey: ["automation-tasks", status, pagination],
  }
}

function TasksTableContent({
  status,
  pagination,
  setPagination,
}: {
  status: AutomationTaskStatus | "all"
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
}) {
  const { data: tasks } = useSuspenseQuery(
    getTasksQueryOptions(status, pagination),
  )
  return (
    <DataTable
      columns={taskColumns}
      data={tasks.data}
      total={tasks.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function TasksTable({
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
      <TasksTableContent
        status={status}
        pagination={pagination}
        setPagination={setPagination}
      />
    </Suspense>
  )
}

export function TasksSection() {
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
        <div className="flex items-center gap-2">
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
          <AddTaskDialog />
        </div>
      </div>
      <TasksTable
        status={status}
        pagination={pagination}
        setPagination={setPagination}
      />
    </div>
  )
}
