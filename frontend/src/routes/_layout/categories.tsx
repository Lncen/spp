import { createFileRoute } from "@tanstack/react-router"
import { ensurePermission } from "@/hooks/usePermissions"
import { ImageCategories } from "../../components/Admin/ImageCategories/ImageCategories"

export const Route = createFileRoute("/_layout/categories")({
  component: RouteComponent,
  beforeLoad: ({ context }) =>
    ensurePermission(context.queryClient, "image_category:view"),
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
