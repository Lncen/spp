import { createFileRoute, redirect } from "@tanstack/react-router"

import { NotificationsSection } from "@/components/Admin/Notifications"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/notifications")({
  component: Notifications,
  beforeLoad: async ({ context }) => {
    const user = await context.queryClient.ensureQueryData(
      getCurrentUserQueryOptions(),
    )
    if (!user.is_superuser) {
      throw redirect({
        to: "/",
      })
    }
  },
  head: () => ({
    meta: [
      {
        title: "通知记录 - SPP",
      },
    ],
  }),
})

function Notifications() {
  return <NotificationsSection />
}
