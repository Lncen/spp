import { zodResolver } from "@hookform/resolvers/zod"
import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import type { SettingRead } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { LoadingButton } from "@/components/ui/loading-button"
import { Textarea } from "@/components/ui/textarea"
import { formatValue, parseValue } from "./utils"

const formSchema = z.object({
  value: z.string().min(1, "值不能为空"),
})

type FormData = z.infer<typeof formSchema>

interface EditValueDialogProps {
  setting: SettingRead
  open: boolean
  isPending: boolean
  onOpenChange: (open: boolean) => void
  onSave: (value: unknown) => void
}

export const EditValueDialog = ({
  setting,
  open,
  isPending,
  onOpenChange,
  onSave,
}: EditValueDialogProps) => {
  const form = useForm<FormData>({
    resolver: zodResolver(formSchema) as any,
    defaultValues: { value: formatValue(setting.value) },
  })

  useEffect(() => {
    if (open) {
      form.reset({ value: formatValue(setting.value) })
    }
  }, [open, setting, form])

  const onSubmit = (data: FormData) => {
    onSave(parseValue(data.value))
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>编辑设置</DialogTitle>
          <DialogDescription>
            以 JSON 格式输入新值，字符串需要加引号
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="flex flex-col gap-4"
          >
            <FormField
              control={form.control}
              name="value"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>值</FormLabel>
                  <FormControl>
                    <Textarea {...field} rows={4} />
                  </FormControl>
                  <FormDescription>
                    示例：true、123、"hello"、{'{ "k": 1 }'}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <DialogFooter className="mt-4">
              <DialogClose asChild>
                <Button type="button" variant="outline" disabled={isPending}>
                  取消
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={isPending}>
                保存
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
