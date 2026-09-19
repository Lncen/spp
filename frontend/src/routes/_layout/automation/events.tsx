import { createFileRoute } from "@tanstack/react-router"

import { EventsSection } from "@/components/Admin/Automation/events"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/automation/events")({
  component: Events,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "automation_event:view"),
  head: () => ({
    meta: [
      {
        title: "自动化事件 - SPP",
      },
    ],
  }),
})

function Events() {
  return <EventsSection />
}
