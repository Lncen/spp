import { createFileRoute, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { PriceTemplates } from "@/components/Admin/PriceTemplates/PriceTemplates"

export const Route = createFileRoute("/_layout/price-templates")({
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
        title: "价格模板 - SPP",
      },
    ],
  }),
})

function RouteComponent() {
  return (
    <div className="flex flex-col gap-6">
      <PriceTemplates />
    </div>
  )
}
