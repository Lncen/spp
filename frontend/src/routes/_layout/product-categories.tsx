import { createFileRoute, redirect } from "@tanstack/react-router"

import { ProductCategories } from "@/components/Admin/ProductCategories/ProductCategories"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/product-categories")({
  component: RouteComponent,
  beforeLoad: async ({ context }) => {
    const user = await context.queryClient.ensureQueryData(getCurrentUserQueryOptions())
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
