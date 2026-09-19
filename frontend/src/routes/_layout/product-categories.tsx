import { createFileRoute } from "@tanstack/react-router"

import { ProductCategories } from "@/components/Admin/ProductCategories/ProductCategories"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/product-categories")({
  component: RouteComponent,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "product_category:view"),
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
