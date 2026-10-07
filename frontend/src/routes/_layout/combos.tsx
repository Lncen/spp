import { createFileRoute } from "@tanstack/react-router"

import { Combos } from "@/components/Combos/Combos"

export const Route = createFileRoute("/_layout/combos")({
  component: RouteComponent,
  head: () => ({
    meta: [
      {
        title: "我的组合 - SPP",
      },
    ],
  }),
})

function RouteComponent() {
  return (
    <div className="flex flex-col gap-6">
      <Combos />
    </div>
  )
}
