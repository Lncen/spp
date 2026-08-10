import { useSuspenseQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
import type { PaginationState } from "@tanstack/react-table"
import { X } from "lucide-react"
import { Suspense, useState } from "react"

import type { OrderStatus } from "@/client"
import { OrdersService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { columns } from "./columns"
import { ORDER_STATUS_OPTIONS } from "./constants"
import PendingOrders from "./PendingOrders"

const ALL_STATUS = "all"

function toOrderStatus(value: string): OrderStatus | undefined {
  if (value === ALL_STATUS) return undefined
  return Number(value) as OrderStatus
}

interface OrdersFilters {
  status: string
}

function getOrdersQueryOptions(
  userId: string | undefined,
  filters: OrdersFilters,
  pagination: PaginationState,
) {
  const status = toOrderStatus(filters.status)
  return {
    queryFn: () =>
      OrdersService.readOrders({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
        status,
        userId: userId ?? null,
      }),
    queryKey: ["orders", userId ?? null, status, pagination],
  }
}

function OrdersTableContent({
  userId,
  filters,
  pagination,
  setPagination,
}: {
  userId: string | undefined
  filters: OrdersFilters
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
}) {
  const { data: orders } = useSuspenseQuery(
    getOrdersQueryOptions(userId, filters, pagination),
  )

  return (
    <DataTable
      columns={columns}
      data={orders.data}
      total={orders.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function OrdersTable({
  userId,
  filters,
  pagination,
  setPagination,
}: {
  userId: string | undefined
  filters: OrdersFilters
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
}) {
  return (
    <Suspense fallback={<PendingOrders />}>
      <OrdersTableContent
        userId={userId}
        filters={filters}
        pagination={pagination}
        setPagination={setPagination}
      />
    </Suspense>
  )
}

export function Orders({ userId }: { userId: string | undefined }) {
  const [filters, setFilters] = useState<OrdersFilters>({
    status: ALL_STATUS,
  })
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })

  const handleStatusChange = (status: string) => {
    setFilters((current) => ({ ...current, status }))
    setPagination((current) => ({ ...current, pageIndex: 0 }))
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight">订单管理</h2>
          <p className="text-muted-foreground">
            查询全部订单，支持按用户和状态筛选
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {userId && (
            <Button variant="outline" size="sm" asChild>
              <RouterLink to="/orders" search={{}}>
                <X />
                清除用户筛选
              </RouterLink>
            </Button>
          )}
          <Select value={filters.status} onValueChange={handleStatusChange}>
            <SelectTrigger className="w-40">
              <SelectValue placeholder="全部状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL_STATUS}>全部状态</SelectItem>
              {ORDER_STATUS_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={String(option.value)}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <OrdersTable
        userId={userId}
        filters={filters}
        pagination={pagination}
        setPagination={setPagination}
      />
    </div>
  )
}
