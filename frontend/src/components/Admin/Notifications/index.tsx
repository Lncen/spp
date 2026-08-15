import { useSuspenseQuery } from "@tanstack/react-query"
import type { PaginationState } from "@tanstack/react-table"
import { Suspense, useState } from "react"

import type { NotificationAdminItem } from "@/client"
import { NotificationsService } from "@/client"
import Pending from "@/components/Admin/Pending/PendingItems"
import { DataTable } from "@/components/Common/DataTable"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { notificationColumns } from "./columns"
import { CHANNEL_LABELS, DELIVERY_STATUS_LABELS } from "./constants"
import { NotificationDetailDialog } from "./NotificationDetailDialog"
import { SendNotificationDialog } from "./SendNotificationDialog"

const ALL = "all"

interface NotificationsFilters {
  channel: string
  status: string
}

function getNotificationsQueryOptions(
  filters: NotificationsFilters,
  pagination: PaginationState,
) {
  return {
    queryFn: () =>
      NotificationsService.readAdminNotifications({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
        channel: filters.channel === ALL ? null : filters.channel,
        status: filters.status === ALL ? null : filters.status,
      }),
    queryKey: ["admin-notifications", filters, pagination],
  }
}

function NotificationsTableContent({
  filters,
  pagination,
  setPagination,
  onView,
}: {
  filters: NotificationsFilters
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
  onView: (item: NotificationAdminItem) => void
}) {
  const { data } = useSuspenseQuery(
    getNotificationsQueryOptions(filters, pagination),
  )

  return (
    <DataTable
      columns={notificationColumns(onView)}
      data={data.data}
      total={data.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function NotificationsTable({
  filters,
  pagination,
  setPagination,
  onView,
}: {
  filters: NotificationsFilters
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
  onView: (item: NotificationAdminItem) => void
}) {
  return (
    <Suspense fallback={<Pending />}>
      <NotificationsTableContent
        filters={filters}
        pagination={pagination}
        setPagination={setPagination}
        onView={onView}
      />
    </Suspense>
  )
}

export function NotificationsSection() {
  const [filters, setFilters] = useState<NotificationsFilters>({
    channel: ALL,
    status: ALL,
  })
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const [selected, setSelected] = useState<NotificationAdminItem | null>(null)

  const handleFilterChange =
    (key: keyof NotificationsFilters) => (value: string) => {
      setFilters((current) => ({ ...current, [key]: value }))
      setPagination((current) => ({ ...current, pageIndex: 0 }))
    }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight">通知记录</h2>
          <p className="text-muted-foreground">
            查看全系统通知与投递状态，支持手动发送与失败重试
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={filters.channel}
            onValueChange={handleFilterChange("channel")}
          >
            <SelectTrigger className="w-32">
              <SelectValue placeholder="全部渠道" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>全部渠道</SelectItem>
              {Object.entries(CHANNEL_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={filters.status}
            onValueChange={handleFilterChange("status")}
          >
            <SelectTrigger className="w-32">
              <SelectValue placeholder="全部状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>全部状态</SelectItem>
              {Object.entries(DELIVERY_STATUS_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <SendNotificationDialog />
        </div>
      </div>
      <NotificationsTable
        filters={filters}
        pagination={pagination}
        setPagination={setPagination}
        onView={setSelected}
      />
      <NotificationDetailDialog
        item={selected}
        onOpenChange={(open) => {
          if (!open) setSelected(null)
        }}
      />
    </div>
  )
}
