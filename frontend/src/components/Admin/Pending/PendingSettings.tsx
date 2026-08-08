import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"

const PendingSettings = () => (
  <div className="flex flex-col">
    {Array.from({ length: 3 }).map((_, index) => (
      <div key={index} className="flex flex-col">
        {index > 0 && <Separator />}
        <div className="flex items-center justify-between gap-4 py-4">
          <div className="flex flex-col gap-2">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-56" />
          </div>
          <Skeleton className="size-8 rounded-full" />
        </div>
      </div>
    ))}
  </div>
)

export default PendingSettings
