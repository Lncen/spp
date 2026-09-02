import { createFileRoute, redirect } from "@tanstack/react-router"

import { RulesSection } from "@/components/Admin/Automation/rules"
import { getCurrentUserQueryOptions } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout/automation/rules")({
  component: Rules,
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
        title: "自动化规则 - SPP",
      },
    ],
  }),
})

function Rules() {
  return <RulesSection />
}
