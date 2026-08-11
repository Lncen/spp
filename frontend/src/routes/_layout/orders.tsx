import { createFileRoute, redirect } from "@tanstack/react-router"
import { z } from "zod"

import { Orders } from "@/components/Admin/Orders/Orders"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

const ordersSearchSchema = z.object({
  user_id: z.string().optional().catch(undefined),
})

export const Route = createFileRoute("/_layout/orders")({
  component: RouteComponent,
  validateSearch: ordersSearchSchema,
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
        title: "订单管理 - SPP",
      },
    ],
  }),
})

function RouteComponent() {
  const { user_id: userId } = Route.useSearch()

  return (
    <div className="flex flex-col gap-6">
      <Orders userId={userId} />
    </div>
  )
}
