import { createFileRoute, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { GlobalSettings } from "@/components/Admin/GlobalSettings/GlobalSettings"

export const Route = createFileRoute("/_layout/global-settings")({
  component: RouteComponent,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
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
