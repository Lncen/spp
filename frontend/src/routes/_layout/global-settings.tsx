import { createFileRoute, redirect } from "@tanstack/react-router"

import { GlobalSettings } from "@/components/Admin/GlobalSettings/GlobalSettings"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/global-settings")({
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
        title: "全局设置 - SPP",
      },
    ],
  }),
})

function RouteComponent() {
  return (
    <div className="flex flex-col gap-6">
      <GlobalSettings />
    </div>
  )
}
