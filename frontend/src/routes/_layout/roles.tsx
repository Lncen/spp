import { createFileRoute } from "@tanstack/react-router"

import { Roles } from "@/components/Admin/Roles"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/roles")({
  component: RouteComponent,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "role:view"),
  head: () => ({
    meta: [
      {
        title: "角色管理 - SPP",
      },
    ],
  }),
})

function RouteComponent() {
  return <Roles />
}
