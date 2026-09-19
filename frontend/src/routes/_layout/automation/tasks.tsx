import { createFileRoute } from "@tanstack/react-router"

import { TasksSection } from "@/components/Admin/Automation/tasks"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/automation/tasks")({
  component: Tasks,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "automation_task:view"),
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
