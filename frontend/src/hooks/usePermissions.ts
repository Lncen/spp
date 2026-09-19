import { type QueryClient, useQuery } from "@tanstack/react-query"
import { redirect } from "@tanstack/react-router"

import { RolesService } from "@/client"

const PERMISSIONS_QUERY_KEY = ["myPermissions"] as const

const permissionsQueryOptions = () => ({
  queryKey: PERMISSIONS_QUERY_KEY,
  queryFn: () => RolesService.readMyPermissions(),
  staleTime: 5 * 60 * 1000,
})

/**
 * 路由守卫：等待权限数据后按权限码判定，未持有则跳回首页。
 * 超级管理员由后端返回全部权限码，无需单独判断。
 */
const ensurePermission = async (
  queryClient: QueryClient,
  code: string,
): Promise<void> => {
  const permissions = await queryClient.ensureQueryData(
    permissionsQueryOptions(),
  )
  const granted =
    permissions.is_superuser || permissions.permission_codes.includes(code)
  if (!granted) {
    throw redirect({ to: "/" })
  }
}

/**
 * 当前用户权限：用于菜单、按钮等前端可见性渲染，真实权限以后端校验为准。
 */
const usePermissions = () => {
  const { data } = useQuery(permissionsQueryOptions())
  const isSuperuser = data?.is_superuser ?? false
  const permissionCodes = data?.permission_codes ?? []

  const hasPermission = (code: string) =>
    isSuperuser || permissionCodes.includes(code)

  const hasAnyPermission = (...codes: string[]) =>
    isSuperuser || codes.some((code) => permissionCodes.includes(code))

  return { isSuperuser, permissionCodes, hasPermission, hasAnyPermission }
}

export { ensurePermission, PERMISSIONS_QUERY_KEY, permissionsQueryOptions }
export default usePermissions
