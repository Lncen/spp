import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import type { PaginationState } from "@tanstack/react-table"
import { Suspense, useState } from "react"

import { type UserPublic, UsersService } from "@/client"
import PendingUsers from "@/components/Admin/Pending/PendingUsers"
import AddUser from "@/components/Admin/Users/AddUser"
import { columns, type UserTableData } from "@/components/Admin/Users/columns"
import { DataTable } from "@/components/Common/DataTable"
import useAuth from "@/hooks/useAuth"

function getUsersQueryOptions(pagination: PaginationState) {
  return {
    queryFn: () =>
      UsersService.readUsers({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
      }),
    queryKey: ["users", pagination],
  }
}

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
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
        title: "用户管理 - SPP",
      },
    ],
  }),
})

function UsersTableContent() {
  const { user: currentUser } = useAuth()
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const { data: users } = useSuspenseQuery(getUsersQueryOptions(pagination))

  const tableData: UserTableData[] = users.data.map((user: UserPublic) => ({
    ...user,
    isCurrentUser: currentUser?.id === user.id,
  }))

  return (
    <DataTable
      columns={columns}
      data={tableData}
      total={users.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function UsersTable() {
  return (
    <Suspense fallback={<PendingUsers />}>
      <UsersTableContent />
    </Suspense>
  )
}

function Admin() {
  return (
    <div className="flex flex-col gap-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">用户管理</h1>
          <p className="text-muted-foreground">管理用户账号与权限</p>
        </div>
        <AddUser />
      </div>
      <UsersTable />
    </div>
  )
}
