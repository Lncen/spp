import { createFileRoute, redirect } from "@tanstack/react-router"

import { PriceTemplates } from "@/components/Admin/PriceTemplates/PriceTemplates"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/price-templates")({
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
