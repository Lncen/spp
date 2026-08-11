import type { ReactNode } from "react"

import { FormItem, FormLabel } from "@/components/ui/form"

export function HorizontalFormItem({
  label,
  required = false,
  children,
}: {
  label: string
  required?: boolean
  children: ReactNode
}) {
  return (
    <FormItem className="flex items-start gap-3">
      <FormLabel className="w-24 shrink-0 pt-2 text-right">
        {label}
        {required && <span className="text-destructive"> *</span>}
      </FormLabel>
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">{children}</div>
    </FormItem>
  )
}

export function DisplayRow({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-24 shrink-0 text-right text-sm font-medium">
        {label}
      </span>
      <div className="flex min-w-0 flex-1 items-center gap-2">{children}</div>
    </div>
  )
}
