import { ChevronDown } from "lucide-react"

import type { RolePublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Skeleton } from "@/components/ui/skeleton"

interface RoleFieldsProps {
  roles?: RolePublic[]
  selectedRoleIds: string[]
  isLoading: boolean
  onChange: (roleIds: string[]) => void
}

/** 用户角色下拉选择：一个用户可同时拥有多个角色 */
export function RoleFields({
  roles,
  selectedRoleIds,
  isLoading,
  onChange,
}: RoleFieldsProps) {
  const selected = new Set(selectedRoleIds)
  const selectedNames =
    roles?.filter((role) => selected.has(role.id)).map((role) => role.name) ??
    []

  const toggleRole = (roleId: string, checked: boolean) => {
    onChange(
      checked
        ? Array.from(new Set([...selectedRoleIds, roleId]))
        : selectedRoleIds.filter((id) => id !== roleId),
    )
  }

  return (
    <div className="flex items-start gap-3">
      <span className="w-24 shrink-0 pt-2 text-right text-sm font-medium">
        角色
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        {isLoading ? (
          <Skeleton className="h-9 w-full" />
        ) : !roles?.length ? (
          <p className="py-2 text-sm text-muted-foreground">暂无可分配的角色</p>
        ) : (
          <>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  className="w-full justify-between font-normal"
                >
                  <span className="truncate">
                    {selectedNames.length
                      ? selectedNames.join("、")
                      : "未分配角色"}
                  </span>
                  <ChevronDown className="text-muted-foreground" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="start"
                className="max-h-72 w-(--radix-dropdown-menu-trigger-width) min-w-56 overflow-y-auto"
              >
                <DropdownMenuLabel>分配角色</DropdownMenuLabel>
                <DropdownMenuSeparator />
                {roles.map((role) => {
                  const isSelected = selected.has(role.id)
                  const isAssignable = role.is_active || isSelected

                  return (
                    <DropdownMenuCheckboxItem
                      key={role.id}
                      checked={isSelected}
                      disabled={!isAssignable}
                      onCheckedChange={(checked) =>
                        toggleRole(role.id, checked)
                      }
                    >
                      <span className="truncate">{role.name}</span>
                      <Badge variant="secondary" className="ml-auto">
                        {role.is_system ? "系统角色" : "自定义角色"}
                      </Badge>
                      {role.is_active ? null : (
                        <Badge variant="outline">已停用</Badge>
                      )}
                    </DropdownMenuCheckboxItem>
                  )
                })}
              </DropdownMenuContent>
            </DropdownMenu>
            <p className="text-xs text-muted-foreground">
              可多选，保存后立即生效；超级管理员拥有全部权限，不受角色限制。
            </p>
          </>
        )}
      </div>
    </div>
  )
}
