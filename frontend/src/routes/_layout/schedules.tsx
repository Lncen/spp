import { createFileRoute } from "@tanstack/react-router"

import { SchedulesSection } from "@/components/Admin/Automation/schedules"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/schedules")({
  component: Schedules,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "schedule:view"),
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
