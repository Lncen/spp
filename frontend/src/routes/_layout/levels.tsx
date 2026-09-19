import { createFileRoute } from "@tanstack/react-router"

import { Levels } from "@/components/Admin/Levels/Levels"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/levels")({
  component: RouteComponent,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "level:view"),
  head: () => ({
    meta: [
      {
        title: "等级 - SPP",
      },
    ],
  }),
})

function RouteComponent() {
  return (
    <div className="flex flex-col gap-6">
      <Levels />
    </div>
  )
}
