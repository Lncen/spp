import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"

import { Orders } from "@/components/Admin/Orders/Orders"
import { ensurePermission } from "@/hooks/usePermissions"

const ordersSearchSchema = z.object({
  user_id: z.string().optional().catch(undefined),
})

export const Route = createFileRoute("/_layout/orders")({
  component: RouteComponent,
  validateSearch: ordersSearchSchema,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "order:view"),
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
