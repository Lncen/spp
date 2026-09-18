import { useQuery } from "@tanstack/react-query"
import { useState } from "react"

import { RolesService } from "@/client"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ROLES_QUERY_KEY } from "./constants"
import PendingRoles from "./PendingRoles"
import { RoleInfoCard } from "./RoleInfoCard"
import { RoleListPanel } from "./RoleListPanel"
import { RolePermissionCard } from "./RolePermissionCard"

/** 角色数量有限，管理端一次性展示（接口上限 100） */
const ROLE_LIST_LIMIT = 100

function rolesQueryOptions() {
  return {
    queryKey: ROLES_QUERY_KEY,
    queryFn: () => RolesService.readRoles({ limit: ROLE_LIST_LIMIT }),
  }
}

export const Roles = () => {
  const { data, isPending } = useQuery(rolesQueryOptions())
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null)

  const roles = data?.data ?? []
  const activeRole =
    roles.find((role) => role.id === selectedRoleId) ?? roles[0]

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-bold tracking-tight">角色管理</h2>
        <p className="text-muted-foreground">
          维护角色信息并分配权限，两项修改相互独立
        </p>
      </div>
      {isPending ? (
        <PendingRoles />
      ) : (
        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,17rem)_minmax(0,1fr)]">
          <RoleListPanel
            roles={roles}
            selectedRoleId={activeRole?.id ?? null}
            onSelect={setSelectedRoleId}
            onCreated={setSelectedRoleId}
          />
          {activeRole ? (
            <div className="flex flex-col gap-6">
              <RoleInfoCard
                role={activeRole}
                onDeleted={() => setSelectedRoleId(null)}
              />
              <RolePermissionCard role={activeRole} />
            </div>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>暂无角色</CardTitle>
                <CardDescription>
                  在左侧点击「创建」新增自定义角色
                </CardDescription>
              </CardHeader>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
