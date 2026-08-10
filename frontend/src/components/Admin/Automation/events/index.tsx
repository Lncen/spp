import { useSuspenseQuery } from "@tanstack/react-query"
import type { PaginationState } from "@tanstack/react-table"
import { Suspense, useState } from "react"

import { AutomationService } from "@/client"
import Pending from "@/components/Admin/Pending/PendingItems"
import { DataTable } from "@/components/Common/DataTable"
import { eventColumns } from "./columns"
import PublishEventDialog from "./PublishEventDialog"

function getEventsQueryOptions(pagination: PaginationState) {
  return {
    queryFn: () =>
      AutomationService.readAutomationEvents({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
      }),
    queryKey: ["automation-events", pagination],
  }
}

function EventsTableContent() {
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const { data: events } = useSuspenseQuery(getEventsQueryOptions(pagination))
  return (
    <DataTable
      columns={eventColumns}
      data={events.data}
      total={events.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function EventsTable() {
  return (
    <Suspense fallback={<Pending />}>
      <EventsTableContent />
    </Suspense>
  )
}

export function EventsSection() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <PublishEventDialog />
      </div>
      <EventsTable />
    </div>
  )
}
