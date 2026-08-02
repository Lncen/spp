import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import { Suspense } from "react"

import type { SupplierPublic } from "@/client"
import { UsersService } from "@/client"
import AddSupplier from "@/components/Admin/Suppliers/AddSupplier"
import { columns } from "@/components/Admin/Suppliers/columns"
import { DataTable } from "@/components/Common/DataTable"
import Pending from "@/components/Admin/Pending/PendingItems"

function getSuppliersQueryOptions() {
  return {
    queryFn: () => import("@/client").then((m) => m.SuppliersService.readSuppliers({ skip: 0, limit: 100 })),
    queryKey: ["suppliers"],
  }
}

export const Route = createFileRoute("/_layout/suppliers")({
  component: Suppliers,
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
        title: "上游管理 - SPP",
      },
    ],
  }),
})

function SuppliersTableContent() {
  const { data: suppliers } = useSuspenseQuery(getSuppliersQueryOptions())

  const tableData: SupplierPublic[] = suppliers.data.map((s: SupplierPublic) => ({
    ...s,
  }))

  return <DataTable columns={columns} data={tableData} />
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">上游管理</h1>
          <p className="text-muted-foreground">
            管理上游 AI API 供应商及其凭证
          </p>
        </div>
        <AddSupplier />
      </div>
      <SuppliersTable />
    </div>
  )
}
