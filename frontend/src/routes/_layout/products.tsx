import { createFileRoute, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { Products } from "@/components/Admin/Products/Products"

export const Route = createFileRoute("/_layout/products")({
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
        title: "商品管理 - SPP",
      },
    ],
  }),
})

function RouteComponent() {
  return (
    <div className="flex flex-col gap-6">
      <Products />
    </div>
  )
}
