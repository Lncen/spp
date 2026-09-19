import { createFileRoute } from "@tanstack/react-router"

import { NotificationsSection } from "@/components/Admin/Notifications"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/notifications")({
  component: Notifications,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "notification:view"),
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
