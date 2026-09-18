import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ChevronRight, Search } from "lucide-react"
import { useMemo, useState } from "react"

import {
  PermissionsService,
  type PermissionTreeCategory,
  type RolePermissionsUpdate,
  type RolePublic,
  RolesService,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"
import { PERMISSION_TREE_QUERY_KEY, rolePermissionsQueryKey } from "./constants"

function usePermissionTree() {
  return useQuery({
    queryKey: PERMISSION_TREE_QUERY_KEY,
    queryFn: () => PermissionsService.readPermissionTree(),
  })
}

function useRolePermissions(roleId: string) {
  return useQuery({
    queryKey: rolePermissionsQueryKey(roleId),
    queryFn: () => RolesService.readRolePermissions({ roleId }),
  })
}

function sameCodes(left: Set<string>, right: Set<string>): boolean {
  if (left.size !== right.size) {
    return false
  }
  return Array.from(left).every((code) => right.has(code))
}

interface RolePermissionCardProps {
  role: RolePublic
}

export function RolePermissionCard({ role }: RolePermissionCardProps) {
  const { data: tree, isPending: isTreePending } = usePermissionTree()
  const { data: rolePermissions, isPending } = useRolePermissions(role.id)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  /** 草稿权限码，为 null 表示与服务器一致；按角色隔离，切换角色后自动失效 */
  const [draftState, setDraftState] = useState<{
    roleId: string
    codes: string[] | null
  }>({ roleId: role.id, codes: null })
  /** 搜索与折叠状态，同样按角色隔离 */
  const [uiState, setUiState] = useState<{
    roleId: string
    keyword: string
    collapsedIds: string[]
  }>({ roleId: role.id, keyword: "", collapsedIds: [] })

  const draftCodes = draftState.roleId === role.id ? draftState.codes : null
  const setDraftCodes = (codes: string[] | null) =>
    setDraftState({ roleId: role.id, codes })

  const ui =
    uiState.roleId === role.id
      ? uiState
      : { roleId: role.id, keyword: "", collapsedIds: [] }
  const keyword = ui.keyword
  const collapsedIds = ui.collapsedIds

  const baselineCodes = useMemo(
    () => rolePermissions?.permission_codes ?? [],
    [rolePermissions],
  )
  const baseline = useMemo(() => new Set(baselineCodes), [baselineCodes])
  const selectedCodes = draftCodes ?? baselineCodes
  const selected = useMemo(() => new Set(selectedCodes), [selectedCodes])
  const isDirty = !sameCodes(selected, baseline)

  /** 权限码 → 权限 ID，保存时接口需要 ID */
  const permissionIdByCode = useMemo(() => {
    const map = new Map<string, string>()
    for (const category of tree?.data ?? []) {
      for (const permission of category.permissions) {
        map.set(permission.code, permission.id)
      }
    }
    return map
  }, [tree])

  const mutation = useMutation({
    mutationFn: (data: RolePermissionsUpdate) =>
      RolesService.setRolePermissionsEndpoint({
        roleId: role.id,
        requestBody: data,
      }),
    onSuccess: (result) => {
      showSuccessToast("角色权限已保存")
      setDraftCodes(result.permission_codes)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({
        queryKey: rolePermissionsQueryKey(role.id),
      })
    },
  })

  const togglePermission = (code: string, checked: boolean) => {
    const current = draftCodes ?? baselineCodes
    setDraftCodes(
      checked
        ? Array.from(new Set([...current, code]))
        : current.filter((item) => item !== code),
    )
  }

  const toggleCategory = (categoryId: string) => {
    setUiState({
      ...ui,
      collapsedIds: collapsedIds.includes(categoryId)
        ? collapsedIds.filter((id) => id !== categoryId)
        : [...collapsedIds, categoryId],
    })
  }

  const onSave = () => {
    mutation.mutate({
      permission_ids: selectedCodes
        .map((code) => permissionIdByCode.get(code))
        .filter((id): id is string => Boolean(id)),
    })
  }

  const onCancel = () => {
    setDraftCodes(null)
  }

  const normalizedKeyword = keyword.trim().toLowerCase()

  const visibleCategories = (tree?.data ?? [])
    .map((category) => ({
      category,
      permissions: normalizedKeyword
        ? category.permissions.filter((permission) =>
            [permission.name, permission.code, permission.description]
              .filter(Boolean)
              .some((text) => text?.toLowerCase().includes(normalizedKeyword)),
          )
        : category.permissions,
    }))
    .filter((item) => item.permissions.length > 0)

  return (
    <Card>
      <CardHeader>
        <CardTitle>权限</CardTitle>
        <CardDescription>
          {role.is_system
            ? "系统内置角色的权限会在初始化脚本执行时按内置清单重置"
            : "勾选该角色可用的权限，保存后立即生效"}
        </CardDescription>
        <CardAction className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!isDirty || mutation.isPending}
            onClick={onCancel}
          >
            取消
          </Button>
          <LoadingButton
            size="sm"
            type="button"
            loading={mutation.isPending}
            disabled={!isDirty}
            onClick={onSave}
          >
            保存
          </LoadingButton>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="relative">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={keyword}
            onChange={(event) =>
              setUiState({ ...ui, keyword: event.target.value })
            }
            placeholder="搜索权限"
            className="pl-9"
            aria-label="搜索权限"
          />
        </div>
        {isPending || isTreePending ? (
          <div className="flex flex-col gap-4">
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-24 w-full" />
            ))}
          </div>
        ) : visibleCategories.length === 0 ? (
          <p className="py-4 text-sm text-muted-foreground">没有匹配的权限</p>
        ) : (
          visibleCategories.map(({ category, permissions }) => (
            <PermissionCategorySection
              key={category.id}
              category={category}
              permissions={permissions}
              selected={selected}
              collapsed={collapsedIds.includes(category.id)}
              isSearching={Boolean(normalizedKeyword)}
              onToggleCategory={toggleCategory}
              onTogglePermission={togglePermission}
            />
          ))
        )}
      </CardContent>
    </Card>
  )
}

interface PermissionCategorySectionProps {
  category: PermissionTreeCategory
  permissions: PermissionTreeCategory["permissions"]
  selected: Set<string>
  collapsed: boolean
  isSearching: boolean
  onToggleCategory: (categoryId: string) => void
  onTogglePermission: (code: string, checked: boolean) => void
}

function PermissionCategorySection({
  category,
  permissions,
  selected,
  collapsed,
  isSearching,
  onToggleCategory,
  onTogglePermission,
}: PermissionCategorySectionProps) {
  const selectedCount = category.permissions.filter((permission) =>
    selected.has(permission.code),
  ).length
  const isExpanded = isSearching || !collapsed

  return (
    <section className="flex flex-col gap-3 rounded-lg border p-4">
      <button
        type="button"
        className="flex items-center gap-2"
        onClick={() => onToggleCategory(category.id)}
      >
        <ChevronRight
          className={cn(
            "size-4 text-muted-foreground transition-transform",
            isExpanded && "rotate-90",
          )}
        />
        <span className="text-sm font-medium">{category.name}</span>
        <span className="ml-auto text-xs tabular-nums text-muted-foreground">
          {selectedCount} / {category.permissions.length}
        </span>
      </button>
      {isExpanded ? (
        <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2 xl:grid-cols-3">
          {permissions.map((permission) => (
            <label
              key={permission.id}
              htmlFor={permission.id}
              className="flex items-center gap-2 text-sm"
            >
              <Checkbox
                id={permission.id}
                checked={selected.has(permission.code)}
                onCheckedChange={(checked) =>
                  onTogglePermission(permission.code, checked === true)
                }
              />
              <span title={permission.code}>{permission.name}</span>
            </label>
          ))}
        </div>
      ) : null}
    </section>
  )
}
