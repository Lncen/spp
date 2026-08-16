import { createFileRoute, redirect } from "@tanstack/react-router"

import { AuditLogsSection } from "@/components/Admin/AuditLogs"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/audit-logs")({
  component: AuditLogs,
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
        title: "操作审计 - SPP",
      },
    ],
  }),
})

function AuditLogs() {
  return <AuditLogsSection />
}
