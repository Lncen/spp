import { createFileRoute, redirect } from "@tanstack/react-router"

import { ArchivesSection } from "@/components/Admin/Automation/archives"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/automation/archives")({
  component: Archives,
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
        title: "任务归档 - SPP",
      },
    ],
  }),
})

function Archives() {
  return <ArchivesSection />
}
