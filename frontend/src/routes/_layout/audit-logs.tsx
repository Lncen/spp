import { createFileRoute } from "@tanstack/react-router"

import { AuditLogsSection } from "@/components/Admin/AuditLogs"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/audit-logs")({
  component: AuditLogs,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "audit_log:view"),
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
