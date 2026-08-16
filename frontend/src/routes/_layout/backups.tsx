import { createFileRoute, redirect } from "@tanstack/react-router"

import { BackupsSection } from "@/components/Admin/Backups/Backups"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/backups")({
  component: RouteComponent,
  beforeLoad: async ({ context }) => {
    const user = await context.queryClient.ensureQueryData(
      getCurrentUserQueryOptions(),
    )
    if (!user.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
  },
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
