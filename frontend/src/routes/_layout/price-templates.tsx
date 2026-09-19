import { createFileRoute } from "@tanstack/react-router"

import { PriceTemplates } from "@/components/Admin/PriceTemplates/PriceTemplates"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/price-templates")({
  component: RouteComponent,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "price_template:view"),
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
