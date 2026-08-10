import { createFileRoute, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { SchedulesSection } from "@/components/Admin/Automation/schedules"

export const Route = createFileRoute("/_layout/schedules")({
  component: Schedules,
  beforeLoad: async () => {
    const user = await UsersService.readUserMe()
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
