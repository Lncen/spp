import { createFileRoute } from "@tanstack/react-router"

import { BackupsSection } from "@/components/Admin/Backups/Backups"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/backups")({
  component: RouteComponent,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "backup:view"),
  head: () => ({
    meta: [
      {
        title: "数据备份 - SPP",
      },
    ],
  }),
})

function RouteComponent() {
  return <BackupsSection />
}
