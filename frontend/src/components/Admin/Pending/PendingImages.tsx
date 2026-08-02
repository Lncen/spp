import { Skeleton } from "@/components/ui/skeleton"

const PendingImages = () => (
  <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
    {Array.from({ length: 8 }).map((_, index) => (
      <div key={index} className="overflow-hidden rounded-xl border">
        <Skeleton className="aspect-[4/3] rounded-none" />
        <div className="flex flex-col gap-1.5 p-3">
          <Skeleton className="h-3.5 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      </div>
    ))}
  </div>
)

export default PendingImages
