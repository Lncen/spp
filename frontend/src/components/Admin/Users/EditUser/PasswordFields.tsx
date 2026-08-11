import { useFormContext } from "react-hook-form"

import { FormControl, FormField, FormMessage } from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import type { FormData } from "./editUserForm"
import { HorizontalFormItem } from "./formParts"

export function PasswordFields() {
  const { control } = useFormContext<FormData>()

  return (
    <div className="flex flex-col gap-4">
      <FormField
        control={control}
        name="password"
        render={({ field }) => (
          <HorizontalFormItem label="设置密码">
            <FormControl>
              <Input placeholder="密码" type="password" {...field} />
            </FormControl>
            <FormMessage />
          </HorizontalFormItem>
        )}
      />

      <FormField
        control={control}
        name="confirm_password"
        render={({ field }) => (
          <HorizontalFormItem label="确认密码">
            <FormControl>
              <Input placeholder="密码" type="password" {...field} />
            </FormControl>
            <FormMessage />
          </HorizontalFormItem>
        )}
      />
    </div>
  )
}
