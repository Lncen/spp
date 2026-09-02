import { useFormContext } from "react-hook-form"

import type { ImagesPublic } from "@/client"
import { FormField } from "@/components/ui/form"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import type { FormData } from "./editUserForm"

interface AvatarFieldsProps {
  avatarImages?: ImagesPublic
  isLoading?: boolean
}

const NONE_VALUE = "none"

export function AvatarFields({ avatarImages, isLoading }: AvatarFieldsProps) {
  const { control, watch } = useFormContext<FormData>()
  const avatarId = watch("avatar_id")
  const selectedAvatar = avatarImages?.data.find(
    (image) => image.id === avatarId,
  )

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4 rounded-lg border p-4">
        {selectedAvatar ? (
          <img
            src={selectedAvatar.url}
            alt={selectedAvatar.filename}
            className="size-16 rounded-full border object-cover"
          />
        ) : (
          <div className="bg-muted text-muted-foreground flex size-16 items-center justify-center rounded-full border text-xs">
            未设置
          </div>
        )}
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-muted-foreground text-sm">当前头像</span>
          <span className="truncate text-sm font-medium">
            {selectedAvatar ? selectedAvatar.filename : "无头像"}
          </span>
        </div>
      </div>

      <FormField
        control={control}
        name="avatar_id"
        render={({ field }) => (
          <div className="flex flex-col gap-3">
            <span className="text-sm font-medium">选择头像</span>
            {isLoading ? (
              <div className="grid grid-cols-4 gap-3 sm:grid-cols-5">
                {Array.from({ length: 10 }).map((_, i) => (
                  <Skeleton
                    key={i}
                    className="aspect-square size-full rounded-xl"
                  />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-4 gap-3 sm:grid-cols-5">
                <button
                  type="button"
                  onClick={() => field.onChange(NONE_VALUE)}
                  className={cn(
                    "bg-muted text-muted-foreground flex aspect-square flex-col items-center justify-center gap-1 rounded-xl border text-xs transition-colors hover:border-primary/50",
                    field.value === NONE_VALUE &&
                      "border-primary bg-primary/5 ring-2 ring-primary/30",
                  )}
                >
                  <span className="text-lg leading-none">∅</span>
                  无头像
                </button>
                {avatarImages?.data.map((image) => (
                  <button
                    key={image.id}
                    type="button"
                    title={image.filename}
                    onClick={() => field.onChange(image.id)}
                    className={cn(
                      "relative aspect-square overflow-hidden rounded-xl border bg-muted transition-all hover:border-primary/50",
                      field.value === image.id &&
                        "border-primary ring-2 ring-primary/30",
                    )}
                  >
                    <img
                      src={image.url}
                      alt={image.filename}
                      className="size-full object-cover"
                    />
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      />
    </div>
  )
}
