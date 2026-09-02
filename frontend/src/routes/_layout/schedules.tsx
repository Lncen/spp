import { createFileRoute, redirect } from "@tanstack/react-router"

import { SchedulesSection } from "@/components/Admin/Automation/schedules"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/schedules")({
  component: Schedules,
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
        title: "计划任务 - SPP",
      },
    ],
  }),
})

function Schedules() {
  return <SchedulesSection />
}
