import { createFileRoute, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { EventsSection } from "@/components/Admin/Automation/events"

export const Route = createFileRoute("/_layout/automation/events")({
  component: Events,
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
        title: "自动化事件 - SPP",
      },
    ],
  }),
})

function Events() {
  return <EventsSection />
}
