import { useSuspenseQuery } from "@tanstack/react-query"
import { Link as RouterLink } from "@tanstack/react-router"
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
) {
  const status = toOrderStatus(filters.status)
  return {
    queryFn: () =>
      OrdersService.readOrders({
        skip: 0,
        limit: 100,
        status,
        userId: userId ?? null,
      }),
    queryKey: ["orders", userId ?? null, status],
  }
}

function OrdersTableContent({
  userId,
  filters,
}: {
  userId: string | undefined
  filters: OrdersFilters
}) {
  const { data: orders } = useSuspenseQuery(
    getOrdersQueryOptions(userId, filters),
  )

  return <DataTable columns={columns} data={orders.data} />
}

function OrdersTable({
  userId,
  filters,
}: {
  userId: string | undefined
  filters: OrdersFilters
}) {
  return (
    <Suspense fallback={<PendingOrders />}>
      <OrdersTableContent userId={userId} filters={filters} />
    </Suspense>
  )
}

export function Orders({ userId }: { userId: string | undefined }) {
  const [filters, setFilters] = useState<OrdersFilters>({
    status: ALL_STATUS,
  })

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
          <Select
            value={filters.status}
            onValueChange={(status) =>
              setFilters((current) => ({ ...current, status }))
            }
          >
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
      <OrdersTable userId={userId} filters={filters} />
    </div>
  )
}
