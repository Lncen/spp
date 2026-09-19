import { createFileRoute } from "@tanstack/react-router"

import { SystemLogsSection } from "@/components/Admin/SystemLogs"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/system-logs")({
  component: SystemLogs,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "system_log:view"),
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
