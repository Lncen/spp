import { createFileRoute } from "@tanstack/react-router"

import { RulesSection } from "@/components/Admin/Automation/rules"
import { ensurePermission } from "@/hooks/usePermissions"

export const Route = createFileRoute("/_layout/automation/rules")({
  component: Rules,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "automation_rule:view"),
  head: () => ({
    meta: [
      {
        title: "自动化规则 - SPP",
      },
    ],
  }),
})

function Rules() {
  return <RulesSection />
}
