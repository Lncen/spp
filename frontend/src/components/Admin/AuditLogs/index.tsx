import { useSuspenseQuery } from "@tanstack/react-query"
import type { PaginationState } from "@tanstack/react-table"
import { Search } from "lucide-react"
import { Suspense, useEffect, useState } from "react"

import { type AuditLogPublic, SystemLogsService } from "@/client"
import Pending from "@/components/Admin/Pending/PendingItems"
import { DataTable } from "@/components/Common/DataTable"
import { Input } from "@/components/ui/input"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { AuditLogDetailDialog } from "./AuditLogDetailDialog"
import { auditLogColumns } from "./columns"

const SEARCH_DEBOUNCE_MS = 300

function getAuditLogsQueryOptions(
  action: string,
  resourceType: string,
  resourceId: string,
  pagination: PaginationState,
  keyword: string,
) {
  return {
    queryFn: () =>
      SystemLogsService.readAuditLogs({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
        action: action || undefined,
        resourceType: resourceType || undefined,
        resourceId: resourceId || undefined,
        keyword: keyword || undefined,
      }),
    queryKey: [
      "audit-logs",
      action,
      resourceType,
      resourceId,
      keyword,
      pagination,
    ],
  }
}

function AuditLogsTableContent({
  action,
  resourceType,
  resourceId,
  pagination,
  setPagination,
  onView,
  keyword,
}: {
  action: string
  resourceType: string
  resourceId: string
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
  onView: (log: AuditLogPublic) => void
  keyword: string
}) {
  const { data } = useSuspenseQuery(
    getAuditLogsQueryOptions(
      action,
      resourceType,
      resourceId,
      pagination,
      keyword,
    ),
  )

  return (
    <DataTable
      columns={auditLogColumns(onView)}
      data={data.data}
      total={data.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function AuditLogsTable({
  action,
  resourceType,
  resourceId,
  pagination,
  setPagination,
  onView,
  keyword,
}: {
  action: string
  resourceType: string
  resourceId: string
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
  onView: (log: AuditLogPublic) => void
  keyword: string
}) {
  return (
    <Suspense fallback={<Pending />}>
      <AuditLogsTableContent
        action={action}
        resourceType={resourceType}
        resourceId={resourceId}
        pagination={pagination}
        setPagination={setPagination}
        onView={onView}
        keyword={keyword}
      />
    </Suspense>
  )
}

export function AuditLogsSection() {
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const [selected, setSelected] = useState<AuditLogPublic | null>(null)
  const [keywordInput, setKeywordInput] = useState("")
  const keyword = useDebouncedValue(keywordInput, SEARCH_DEBOUNCE_MS)
  const [actionInput, setActionInput] = useState("")
  const action = useDebouncedValue(actionInput, SEARCH_DEBOUNCE_MS)
  const [resourceTypeInput, setResourceTypeInput] = useState("")
  const resourceType = useDebouncedValue(resourceTypeInput, SEARCH_DEBOUNCE_MS)
  const [resourceIdInput, setResourceIdInput] = useState("")
  const resourceId = useDebouncedValue(resourceIdInput, SEARCH_DEBOUNCE_MS)

  useEffect(() => {
    if (keyword || action || resourceType || resourceId) {
      setPagination((current) => ({ ...current, pageIndex: 0 }))
    }
  }, [keyword, action, resourceType, resourceId])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight">操作审计</h2>
          <p className="text-muted-foreground">
            查看管理员对关键数据做了什么操作
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={keywordInput}
              onChange={(event) => setKeywordInput(event.target.value)}
              placeholder="搜索操作者 / 操作 / 资源"
              className="w-56 pl-9"
            />
          </div>
          <Input
            value={actionInput}
            onChange={(event) => setActionInput(event.target.value)}
            placeholder="操作类型"
            className="w-36"
          />
          <Input
            value={resourceTypeInput}
            onChange={(event) => setResourceTypeInput(event.target.value)}
            placeholder="对象类型"
            className="w-32"
          />
          <Input
            value={resourceIdInput}
            onChange={(event) => setResourceIdInput(event.target.value)}
            placeholder="对象 ID"
            className="w-40"
          />
        </div>
      </div>
      <AuditLogsTable
        action={action}
        resourceType={resourceType}
        resourceId={resourceId}
        pagination={pagination}
        setPagination={setPagination}
        onView={setSelected}
        keyword={keyword}
      />
      <AuditLogDetailDialog
        log={selected}
        onOpenChange={(open) => {
          if (!open) setSelected(null)
        }}
      />
    </div>
  )
}
