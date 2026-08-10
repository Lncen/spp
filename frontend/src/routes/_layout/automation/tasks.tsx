import { createFileRoute, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { TasksSection } from "@/components/Admin/Automation/tasks"

export const Route = createFileRoute("/_layout/automation/tasks")({
  component: Tasks,
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
        title: "任务池 - SPP",
      },
    ],
  }),
})

function Tasks() {
  return <TasksSection />
}
