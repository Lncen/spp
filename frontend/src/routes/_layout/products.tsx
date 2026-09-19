import { createFileRoute } from "@tanstack/react-router"

import { Products } from "@/components/Admin/Products/Products"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/products")({
  component: RouteComponent,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "product:view"),
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
