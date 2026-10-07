import { createFileRoute } from "@tanstack/react-router"

import { Favorites } from "@/components/Favorites/Favorites"

export const Route = createFileRoute("/_layout/favorites")({
  component: RouteComponent,
  head: () => ({
    meta: [
      {
        title: "我的收藏 - SPP",
      },
    ],
  }),
})

function RouteComponent() {
  return (
    <div className="flex flex-col gap-6">
      <Favorites />
    </div>
  )
}
