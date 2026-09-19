import { createFileRoute } from "@tanstack/react-router"

import { GlobalSettings } from "@/components/Admin/GlobalSettings/GlobalSettings"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/global-settings")({
  component: RouteComponent,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "setting:update"),
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
