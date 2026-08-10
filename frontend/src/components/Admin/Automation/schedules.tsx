import { useSuspenseQuery } from "@tanstack/react-query"
import type { PaginationState } from "@tanstack/react-table"
import { Suspense, useState } from "react"

import type { SchedulePublic } from "@/client"
import { SchedulesService } from "@/client"
import Pending from "@/components/Admin/Pending/PendingItems"
import AddSchedule from "@/components/Admin/Schedules/AddSchedule"
import { columns } from "@/components/Admin/Schedules/columns"
import { DataTable } from "@/components/Common/DataTable"

export function getSchedulesQueryOptions(pagination: PaginationState) {
  return {
    queryFn: () =>
      SchedulesService.readSchedules({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
      }),
    queryKey: ["schedules", pagination],
  }
}

function SchedulesTableContent() {
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const { data: schedules } = useSuspenseQuery(
    getSchedulesQueryOptions(pagination),
  )

  const tableData: SchedulePublic[] = schedules.data.map(
    (s: SchedulePublic) => ({
      ...s,
    }),
  )

  return (
    <DataTable
      columns={columns}
      data={tableData}
      total={schedules.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function SchedulesTable() {
  return (
    <Suspense fallback={<Pending />}>
      <SchedulesTableContent />
    </Suspense>
  )
}

export function SchedulesSection() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">计划任务</h2>
          <p className="text-sm text-muted-foreground">
            管理 Celery beat 定时任务、调度规则与立即执行。
          </p>
        </div>
        <AddSchedule />
      </div>
      <SchedulesTable />
    </div>
  )
}
