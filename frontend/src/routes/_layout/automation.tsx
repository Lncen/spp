import { createFileRoute, Outlet } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/automation")({
  component: AutomationLayout,
})

export function AutomationLayout() {
  return <Outlet />
}
