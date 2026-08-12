import { useFormContext } from "react-hook-form"

import type { ImagesPublic, WalletPublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import { FormControl, FormField, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import type { FormData } from "./editUserForm"
import { formatBalance } from "./format"
import { HorizontalFormItem } from "./formParts"

interface BasicInfoFieldsProps {
  avatarImages?: ImagesPublic
  wallet?: WalletPublic
  isWalletLoading: boolean
  levelName?: string | null
}

export function BasicInfoFields({
  avatarImages,
  wallet,
  isWalletLoading,
  levelName,
}: BasicInfoFieldsProps) {
  const { control, watch } = useFormContext<FormData>()
  const avatarId = watch("avatar_id")
  const selectedAvatar = avatarImages?.data.find(
    (image) => image.id === avatarId,
  )
  const fullName = watch("full_name")

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-4">
        {selectedAvatar ? (
          <img
            src={selectedAvatar.url}
            alt={selectedAvatar.filename}
            className="size-18 rounded-full border object-cover"
          />
        ) : (
          <div className="bg-muted text-muted-foreground flex size-18 items-center justify-center rounded-full border text-xs">
            <span className="truncate text-sm">未设置</span>
          </div>
        )}
        <div className="flex flex-col items-start gap-1">
          <span className="truncate text-lg font-medium">
            {fullName || "昵称未填写"}
          </span>
          {levelName && (
            <Badge variant="secondary" className="text-xs">
              {`Lv : ${levelName}`}
            </Badge>
          )}
        </div>
      </div>
      <Separator />

      <FormField
        control={control}
        name="full_name"
        render={({ field }) => (
          <HorizontalFormItem label="昵称">
            <FormControl>
              <Input placeholder="昵称" type="text" {...field} />
            </FormControl>
            <FormMessage />
          </HorizontalFormItem>
        )}
      />

      <FormField
        control={control}
        name="username"
        render={({ field }) => (
          <HorizontalFormItem label="用户名" required>
            <FormControl>
              <Input placeholder="用户名" type="text" {...field} required />
            </FormControl>
            <FormMessage />
          </HorizontalFormItem>
        )}
      />

      <FormField
        control={control}
        name="email"
        render={({ field }) => (
          <HorizontalFormItem label="邮箱">
            <FormControl>
              <Input placeholder="邮箱" type="email" {...field} />
            </FormControl>
            <FormMessage />
          </HorizontalFormItem>
        )}
      />

      <FormField
        control={control}
        name="bio"
        render={({ field }) => (
          <HorizontalFormItem label="简介">
            <FormControl>
              <Textarea
                placeholder="用户简介"
                rows={3}
                maxLength={1000}
                {...field}
              />
            </FormControl>
            <FormMessage />
          </HorizontalFormItem>
        )}
      />

      <FormField
        control={control}
        name="remark"
        render={({ field }) => (
          <HorizontalFormItem label="备注">
            <FormControl>
              <Textarea
                placeholder="管理员备注"
                rows={2}
                maxLength={255}
                {...field}
              />
            </FormControl>
            <FormMessage />
          </HorizontalFormItem>
        )}
      />

      <Separator />

      <div className="flex items-center justify-between rounded-lg border p-4">
        <div className="flex flex-col gap-1">
          <span className="text-muted-foreground text-sm">钱包</span>
          {isWalletLoading ? (
            <Skeleton className="h-8 w-32" />
          ) : (
            <span className="text-2xl font-semibold">
              {formatBalance(wallet?.balance)}
            </span>
          )}
        </div>
        <Badge
          variant={wallet?.is_active === false ? "destructive" : "secondary"}
        >
          {wallet?.is_active === false ? "已禁用" : "正常"}
        </Badge>
      </div>
    </div>
  )
}
