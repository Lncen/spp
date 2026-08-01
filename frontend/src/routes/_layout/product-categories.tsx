import { createFileRoute, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { ProductCategories } from "@/components/ProductCategories/ProductCategories"

export const Route = createFileRoute("/_layout/product-categories")({
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
        title: "商品分类 - SPP",
      },
    ],
  }),
})

function RouteComponent() {
  return (
    <div className="flex flex-col gap-6">
      <ProductCategories />
    </div>
  )
}
