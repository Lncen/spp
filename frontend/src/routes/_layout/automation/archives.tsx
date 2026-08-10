import { createFileRoute, redirect } from "@tanstack/react-router"

import { UsersService } from "@/client"
import { ArchivesSection } from "@/components/Admin/Automation/archives"

export const Route = createFileRoute("/_layout/automation/archives")({
  component: Archives,
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
        title: "任务归档 - SPP",
      },
    ],
  }),
})

function Archives() {
  return <ArchivesSection />
}
