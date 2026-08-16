import { createFileRoute, redirect } from "@tanstack/react-router"

import { SystemLogsSection } from "@/components/Admin/SystemLogs"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/system-logs")({
  component: SystemLogs,
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
        title: "系统日志 - SPP",
      },
    ],
  }),
})

function SystemLogs() {
  return <SystemLogsSection />
}
