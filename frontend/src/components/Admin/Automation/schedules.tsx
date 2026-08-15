import { useSuspenseQuery } from "@tanstack/react-query"
import type { PaginationState } from "@tanstack/react-table"
import { Suspense, useState } from "react"

import type { SchedulePublic } from "@/client"
import { SchedulesService } from "@/client"
import Pending from "@/components/Admin/Pending/PendingItems"
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
      <SchedulesTable />
    </div>
  )
}
