import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute, redirect } from "@tanstack/react-router"
import type { PaginationState } from "@tanstack/react-table"
import { Search } from "lucide-react"
import { Suspense, useState } from "react"

import { type UserListItemPublic, UsersService } from "@/client"
import PendingUsers from "@/components/Admin/Pending/PendingUsers"
import AddUser from "@/components/Admin/Users/AddUser"
import { columns, type UserTableData } from "@/components/Admin/Users/columns"
import { DataTable } from "@/components/Common/DataTable"
import { Input } from "@/components/ui/input"
import useAuth, { getCurrentUserQueryOptions } from "@/hooks/useAuth"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"

const SEARCH_DEBOUNCE_MS = 300

function getUsersQueryOptions(search: string, pagination: PaginationState) {
  return {
    queryFn: () =>
      UsersService.readUsers({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
        search: search || undefined,
      }),
    queryKey: ["users", search, pagination],
  }
}

export const Route = createFileRoute("/_layout/admin")({
  component: Admin,
  beforeLoad: async ({ context }) => {
    const user = await context.queryClient.ensureQueryData(
      getCurrentUserQueryOptions(),
    )
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

function UsersTableContent({ search }: { search: string }) {
  const { user: currentUser } = useAuth()
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const { data: users } = useSuspenseQuery(
    getUsersQueryOptions(search, pagination),
  )

  const tableData: UserTableData[] = users.data.map(
    (user: UserListItemPublic) => ({
      ...user,
      isCurrentUser: currentUser?.id === user.id,
    }),
  )

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

function UsersTable({ search }: { search: string }) {
  return (
    <Suspense fallback={<PendingUsers />}>
      <UsersTableContent search={search} />
    </Suspense>
  )
}

function Admin() {
  const [searchInput, setSearchInput] = useState("")
  const search = useDebouncedValue(searchInput, SEARCH_DEBOUNCE_MS)

  return (
    <div className="flex flex-col gap-10">
      <div className="flex items-center justify-between gap-4">
        <div className="relative w-full max-w-sm">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="搜索用户名 / 邮箱 / 昵称"
            className="pl-9"
          />
        </div>
        <AddUser />
      </div>
      <UsersTable key={search} search={search} />
    </div>
  )
}
