import { createFileRoute, redirect } from "@tanstack/react-router"

import { Roles } from "@/components/Admin/Roles"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/roles")({
  component: RouteComponent,
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
        title: "角色管理 - SPP",
      },
    ],
  }),
})

function RouteComponent() {
  return <Roles />
}
