import { useSuspenseQuery } from "@tanstack/react-query"
import type { PaginationState } from "@tanstack/react-table"
import { Search } from "lucide-react"
import { Suspense, useEffect, useState } from "react"

import type { NotificationAdminItem } from "@/client"
import { NotificationsService } from "@/client"
import Pending from "@/components/Admin/Pending/PendingItems"
import { DataTable } from "@/components/Common/DataTable"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { notificationColumns } from "./columns"
import { CHANNEL_LABELS, DELIVERY_STATUS_LABELS } from "./constants"
import { NotificationDetailDialog } from "./NotificationDetailDialog"
import { SendNotificationDialog } from "./SendNotificationDialog"

const ALL = "all"
const SEARCH_DEBOUNCE_MS = 300

interface NotificationsFilters {
  channel: string
  status: string
}

function getNotificationsQueryOptions(
  filters: NotificationsFilters,
  pagination: PaginationState,
  keyword: string,
  recipient: string,
) {
  return {
    queryFn: () =>
      NotificationsService.readAdminNotifications({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
        channel: filters.channel === ALL ? null : filters.channel,
        status: filters.status === ALL ? null : filters.status,
        keyword: keyword || undefined,
        recipient: recipient || undefined,
      }),
    queryKey: ["admin-notifications", filters, keyword, recipient, pagination],
  }
}

function NotificationsTableContent({
  filters,
  pagination,
  setPagination,
  onView,
  keyword,
  recipient,
}: {
  filters: NotificationsFilters
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
  onView: (item: NotificationAdminItem) => void
  keyword: string
  recipient: string
}) {
  const { data } = useSuspenseQuery(
    getNotificationsQueryOptions(filters, pagination, keyword, recipient),
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
  keyword,
  recipient,
}: {
  filters: NotificationsFilters
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
  onView: (item: NotificationAdminItem) => void
  keyword: string
  recipient: string
}) {
  return (
    <Suspense fallback={<Pending />}>
      <NotificationsTableContent
        filters={filters}
        pagination={pagination}
        setPagination={setPagination}
        onView={onView}
        keyword={keyword}
        recipient={recipient}
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
  const [keywordInput, setKeywordInput] = useState("")
  const keyword = useDebouncedValue(keywordInput, SEARCH_DEBOUNCE_MS)
  const [recipientInput, setRecipientInput] = useState("")
  const recipient = useDebouncedValue(recipientInput, SEARCH_DEBOUNCE_MS)

  const handleFilterChange =
    (key: keyof NotificationsFilters) => (value: string) => {
      setFilters((current) => ({ ...current, [key]: value }))
      setPagination((current) => ({ ...current, pageIndex: 0 }))
    }

  useEffect(() => {
    if (keyword || recipient) {
      setPagination((current) => ({ ...current, pageIndex: 0 }))
    }
  }, [keyword, recipient])

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
          <div className="relative">
            <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={keywordInput}
              onChange={(event) => setKeywordInput(event.target.value)}
              placeholder="搜索标题 / 内容"
              className="w-48 pl-9"
            />
          </div>
          <div className="relative">
            <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={recipientInput}
              onChange={(event) => setRecipientInput(event.target.value)}
              placeholder="搜索接收人"
              className="w-44 pl-9"
            />
          </div>
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
        keyword={keyword}
        recipient={recipient}
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
