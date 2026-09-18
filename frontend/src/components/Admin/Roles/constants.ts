/** 角色列表查询键 */
export const ROLES_QUERY_KEY = ["roles"] as const

/** 单个角色已持有权限的查询键 */
export const rolePermissionsQueryKey = (roleId: string) =>
  ["role-permissions", roleId] as const

/** 权限树查询键 */
export const PERMISSION_TREE_QUERY_KEY = ["permission-tree"] as const

/** 角色类型展示文案 */
export function roleTypeLabel(isSystem: boolean): string {
  return isSystem ? "系统角色" : "自定义角色"
}
