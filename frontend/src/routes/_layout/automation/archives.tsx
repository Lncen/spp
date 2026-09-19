import { createFileRoute } from "@tanstack/react-router"

import { ArchivesSection } from "@/components/Admin/Automation/archives"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/automation/archives")({
  component: Archives,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "automation_task:view"),
  head: () => ({
    meta: [
      {
        title: "任务归档 - SPP",
      },
    ],
  }),
})

function Archives() {
  return <ArchivesSection />
}
