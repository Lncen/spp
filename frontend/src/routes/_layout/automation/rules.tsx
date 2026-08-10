import { createFileRoute, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { RulesSection } from "@/components/Admin/Automation/rules"

export const Route = createFileRoute("/_layout/automation/rules")({
  component: Rules,
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
        title: "自动化规则 - SPP",
      },
    ],
  }),
})

function Rules() {
  return <RulesSection />
}
