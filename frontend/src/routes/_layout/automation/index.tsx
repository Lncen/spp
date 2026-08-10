import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/automation/")({
  beforeLoad: () => {
    throw redirect({
      to: "/automation/tasks",
    })
  },
})
