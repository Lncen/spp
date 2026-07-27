import { useSuspenseQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Image } from "lucide-react"
import { Suspense } from "react"

import { ImagesService } from "@/client"
import { ImageCard } from "@/components/Images/ImageCard"
import UploadImage from "@/components/Images/UploadImage"
import PendingImages from "@/components/Pending/PendingImages"

function getImagesQueryOptions() {
  return {
    queryFn: () => ImagesService.readImages({ skip: 0, limit: 100 }),
    queryKey: ["images"],
  }
}

export const Route = createFileRoute("/_layout/images")({
  component: Images,
  head: () => ({
    meta: [
      {
        title: "Images - FastAPI Template",
      },
    ],
  }),
})

function ImagesTableContent() {
  const { data: images } = useSuspenseQuery(getImagesQueryOptions())

  if (images.data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Image className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">还没有图片</h3>
        <p className="text-muted-foreground">上传一张图片开始使用</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
      {images.data.map((image) => (
        <ImageCard key={image.id} image={image} />
      ))}
    </div>
  )
}

function ImagesTable() {
  return (
    <Suspense fallback={<PendingImages />}>
      <ImagesTableContent />
    </Suspense>
  )
}

function Images() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">图片管理</h1>
          <p className="text-muted-foreground">上传和管理你的图片资源</p>
        </div>
        <UploadImage />
      </div>
      <ImagesTable />
    </div>
  )
}
