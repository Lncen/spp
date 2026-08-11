import { useFormContext } from "react-hook-form"

import { Checkbox } from "@/components/ui/checkbox"
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from "@/components/ui/form"
import type { FormData } from "./editUserForm"

export function PermissionsFields() {
  const { control } = useFormContext<FormData>()

  return (
    <div className="flex flex-col gap-3">
      <FormField
        control={control}
        name="is_superuser"
        render={({ field }) => (
          <FormItem className="flex items-center gap-3">
            <FormLabel className="w-24 shrink-0 text-right font-normal">
              超级管理员
            </FormLabel>
            <FormControl>
              <Checkbox
                checked={field.value}
                onCheckedChange={field.onChange}
              />
            </FormControl>
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name="is_active"
        render={({ field }) => (
          <FormItem className="flex items-center gap-3">
            <FormLabel className="w-24 shrink-0 text-right font-normal">
              启用账号
            </FormLabel>
            <FormControl>
              <Checkbox
                checked={field.value}
                onCheckedChange={field.onChange}
              />
            </FormControl>
          </FormItem>
        )}
      />

      <FormField
        control={control}
        name="can_order"
        render={({ field }) => (
          <FormItem className="flex items-center gap-3">
            <FormLabel className="w-24 shrink-0 text-right font-normal">
              允许下单
            </FormLabel>
            <FormControl>
              <Checkbox
                checked={field.value}
                onCheckedChange={field.onChange}
              />
            </FormControl>
          </FormItem>
        )}
      />
    </div>
  )
}
