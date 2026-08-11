import { createFileRoute, redirect } from "@tanstack/react-router"

import { TasksSection } from "@/components/Admin/Automation/tasks"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/automation/tasks")({
  component: Tasks,
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
        title: "任务池 - SPP",
      },
    ],
  }),
})

function Tasks() {
  return <TasksSection />
}
