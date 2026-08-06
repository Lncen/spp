import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Suspense } from "react"

import type { SchedulePublic } from "@/client"
import { SchedulesService, UsersService } from "@/client"
import Pending from "@/components/Admin/Pending/PendingItems"
import AddSchedule from "@/components/Admin/Schedules/AddSchedule"
import { columns } from "@/components/Admin/Schedules/columns"
import FailedRuns from "@/components/Admin/Schedules/FailedRuns"
import { DataTable } from "@/components/Common/DataTable"

function getSchedulesQueryOptions() {
  return {
    queryFn: () => SchedulesService.readSchedules({ skip: 0, limit: 100 }),
    queryKey: ["schedules"],
  }
}

export const Route = createFileRoute("/_layout/schedules")({
  component: Schedules,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
    if (!user.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "计划任务 - SPP",
      },
    ],
  }),
})

function SchedulesTableContent() {
  const { data: schedules } = useSuspenseQuery(getSchedulesQueryOptions())

  const tableData: SchedulePublic[] = schedules.data.map(
    (s: SchedulePublic) => ({
      ...s,
    }),
  )

  return <DataTable columns={columns} data={tableData} />
}

function SchedulesTable() {
  return (
    <Suspense fallback={<Pending />}>
      <SchedulesTableContent />
    </Suspense>
  )
}

function Schedules() {
  return (
    <div className="flex flex-col gap-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">计划任务</h1>
          <p className="text-muted-foreground">
            管理 Celery beat 定时任务、调度规则与立即执行。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <FailedRuns />
          <AddSchedule />
        </div>
      </div>
      <SchedulesTable />
    </div>
  )
}
