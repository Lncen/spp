import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import type { PaginationState } from "@tanstack/react-table"
import { Search } from "lucide-react"
import { Suspense, useState } from "react"

import { ItemsService } from "@/client"
import AddItem from "@/components/Admin/Items/AddItem"
import { columns } from "@/components/Admin/Items/columns"
import PendingItems from "@/components/Admin/Pending/PendingItems"
import { DataTable } from "@/components/Common/DataTable"

function getItemsQueryOptions(pagination: PaginationState) {
  return {
    queryFn: () =>
      ItemsService.readItems({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
      }),
    queryKey: ["items", pagination],
  }
}

export const Route = createFileRoute("/_layout/items")({
  component: Items,
  head: () => ({
    meta: [
      {
        title: "Items - FastAPI Template",
      },
    ],
  }),
})

function ItemsTableContent() {
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const { data: items } = useSuspenseQuery(getItemsQueryOptions(pagination))

  if (items.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Search className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">You don't have any items yet</h3>
        <p className="text-muted-foreground">Add a new item to get started</p>
      </div>
    )
  }

  return (
    <DataTable
      columns={columns}
      data={items.data}
      total={items.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function ItemsTable() {
  return (
    <Suspense fallback={<PendingItems />}>
      <ItemsTableContent />
    </Suspense>
  )
}

function Items() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-end">
        <AddItem />
      </div>
      <ItemsTable />
    </div>
  )
}
