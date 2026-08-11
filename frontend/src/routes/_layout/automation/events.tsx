import { createFileRoute, redirect } from "@tanstack/react-router"

import { EventsSection } from "@/components/Admin/Automation/events"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/automation/events")({
  component: Events,
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
        title: "自动化事件 - SPP",
      },
    ],
  }),
})

function Events() {
  return <EventsSection />
}
