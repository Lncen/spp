import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import type { PaginationState } from "@tanstack/react-table"
import { Suspense, useState } from "react"

import type { SupplierPublic } from "@/client"
import Pending from "@/components/Admin/Pending/PendingItems"
import AddSupplier from "@/components/Admin/Suppliers/AddSupplier"
import { columns } from "@/components/Admin/Suppliers/columns"
import { DataTable } from "@/components/Common/DataTable"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

function getSuppliersQueryOptions(pagination: PaginationState) {
  return {
    queryFn: () =>
      import("@/client").then((m) =>
        m.SuppliersService.readSuppliers({
          skip: pagination.pageIndex * pagination.pageSize,
          limit: pagination.pageSize,
        }),
      ),
    queryKey: ["suppliers", pagination],
  }
}

export const Route = createFileRoute("/_layout/suppliers")({
  component: Suppliers,
  beforeLoad: async ({ context }) => {
    const user = await context.queryClient.ensureQueryData(getCurrentUserQueryOptions())
    if (!user.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "上游管理 - SPP",
      },
    ],
  }),
})

function SuppliersTableContent() {
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const { data: suppliers } = useSuspenseQuery(
    getSuppliersQueryOptions(pagination),
  )

  const tableData: SupplierPublic[] = suppliers.data.map(
    (s: SupplierPublic) => ({
      ...s,
    }),
  )

  return (
    <DataTable
      columns={columns}
      data={tableData}
      total={suppliers.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function SuppliersTable() {
  return (
    <Suspense fallback={<Pending />}>
      <SuppliersTableContent />
    </Suspense>
  )
}

function Suppliers() {
  return (
    <div className="flex flex-col gap-10">
      <div className="flex items-center justify-end">
        <AddSupplier />
      </div>
      <SuppliersTable />
    </div>
  )
}
