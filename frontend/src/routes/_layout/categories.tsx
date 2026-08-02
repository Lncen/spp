import { createFileRoute, redirect } from "@tanstack/react-router"
import { UsersService } from "@/client"
import { ImageCategories } from "../../components/Admin/ImageCategories/ImageCategories"

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
      <ImageCategories />
    </div>
  )
}
