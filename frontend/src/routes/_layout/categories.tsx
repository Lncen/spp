import { createFileRoute, redirect } from "@tanstack/react-router"

import { ImageCategories } from "../../components/Admin/ImageCategories/ImageCategories"
import { UsersService } from "@/client"

export const Route = createFileRoute("/_layout/categories")({
  component: RouteComponent,
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
        title: "Image Categories",
      },
    ],
  }),
})

function RouteComponent() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Image Categories</h1>
        <p className="text-muted-foreground">
          Manage image classification categories
        </p>
      </div>
      <ImageCategories />
    </div>
  )
}
