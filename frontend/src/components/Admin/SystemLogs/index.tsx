import { useSuspenseQuery } from "@tanstack/react-query"
import type { PaginationState } from "@tanstack/react-table"
import { Search } from "lucide-react"
import { Suspense, useEffect, useState } from "react"

import { type SystemLogPublic, SystemLogsService } from "@/client"
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
import { systemLogColumns } from "./columns"
import { LOG_LEVEL_LABELS, LOG_STATUS_LABELS } from "./constants"
import { SystemLogDetailDialog } from "./SystemLogDetailDialog"

const ALL = "all"
const SEARCH_DEBOUNCE_MS = 300

interface SystemLogFilters {
  level: string
  status: string
}

function getSystemLogsQueryOptions(
  filters: SystemLogFilters,
  pagination: PaginationState,
  keyword: string,
  module: string,
) {
  return {
    queryFn: () =>
      SystemLogsService.readSystemLogs({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
        level: filters.level === ALL ? null : filters.level,
        status: filters.status === ALL ? null : filters.status,
        module: module || undefined,
        keyword: keyword || undefined,
      }),
    queryKey: ["system-logs", filters, keyword, module, pagination],
  }
}

function SystemLogsTableContent({
  filters,
  pagination,
  setPagination,
  onView,
  keyword,
  module,
}: {
  filters: SystemLogFilters
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
  onView: (log: SystemLogPublic) => void
  keyword: string
  module: string
}) {
  const { data } = useSuspenseQuery(
    getSystemLogsQueryOptions(filters, pagination, keyword, module),
  )

  return (
    <DataTable
      columns={systemLogColumns(onView)}
      data={data.data}
      total={data.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function SystemLogsTable({
  filters,
  pagination,
  setPagination,
  onView,
  keyword,
  module,
}: {
  filters: SystemLogFilters
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
  onView: (log: SystemLogPublic) => void
  keyword: string
  module: string
}) {
  return (
    <Suspense fallback={<Pending />}>
      <SystemLogsTableContent
        filters={filters}
        pagination={pagination}
        setPagination={setPagination}
        onView={onView}
        keyword={keyword}
        module={module}
      />
    </Suspense>
  )
}

export function SystemLogsSection() {
  const [filters, setFilters] = useState<SystemLogFilters>({
    level: ALL,
    status: ALL,
  })
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const [selected, setSelected] = useState<SystemLogPublic | null>(null)
  const [keywordInput, setKeywordInput] = useState("")
  const keyword = useDebouncedValue(keywordInput, SEARCH_DEBOUNCE_MS)
  const [moduleInput, setModuleInput] = useState("")
  const module = useDebouncedValue(moduleInput, SEARCH_DEBOUNCE_MS)

  const handleFilterChange =
    (key: keyof SystemLogFilters) => (value: string) => {
      setFilters((current) => ({ ...current, [key]: value }))
      setPagination((current) => ({ ...current, pageIndex: 0 }))
    }

  useEffect(() => {
    if (keyword || module) {
      setPagination((current) => ({ ...current, pageIndex: 0 }))
    }
  }, [keyword, module])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight">系统日志</h2>
          <p className="text-muted-foreground">
            按事件、模块、级别和结果追踪系统发生了什么
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={keywordInput}
              onChange={(event) => setKeywordInput(event.target.value)}
              placeholder="搜索事件 / 资源 / 错误"
              className="w-56 pl-9"
            />
          </div>
          <Input
            value={moduleInput}
            onChange={(event) => setModuleInput(event.target.value)}
            placeholder="模块"
            className="w-32"
          />
          <Select
            value={filters.level}
            onValueChange={handleFilterChange("level")}
          >
            <SelectTrigger className="w-32">
              <SelectValue placeholder="全部级别" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>全部级别</SelectItem>
              {Object.entries(LOG_LEVEL_LABELS).map(([value, label]) => (
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
              <SelectValue placeholder="全部结果" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>全部结果</SelectItem>
              {Object.entries(LOG_STATUS_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <SystemLogsTable
        filters={filters}
        pagination={pagination}
        setPagination={setPagination}
        onView={setSelected}
        keyword={keyword}
        module={module}
      />
      <SystemLogDetailDialog
        log={selected}
        onOpenChange={(open) => {
          if (!open) setSelected(null)
        }}
      />
    </div>
  )
}
