import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Controller, useForm } from "react-hook-form"
import { z } from "zod"

import { NotificationsService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { DialogClose, DialogFooter } from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { CHANNEL_LABELS, EVENT_TYPE_LABELS } from "./constants"

const formSchema = z.object({
  title: z.string().min(1, "请输入通知标题").max(255),
  content: z.string().max(2000),
  event_type: z.string().min(1, "请选择事件类型").max(64),
  channels: z.array(z.string()).min(1, "请至少选择一个渠道"),
})

type FormData = z.infer<typeof formSchema>

function toggleValue(values: string[], value: string, checked: boolean) {
  return checked ? [...values, value] : values.filter((item) => item !== value)
}

interface SendNotificationFormProps {
  /** 群发模式：broadcast=true 发给全部启用用户 */
  broadcast?: boolean
  /** 单用户发送：固定接收用户 ID */
  fixedUserIds?: string[]
  /** 发送成功后回调（关闭弹窗/菜单） */
  onSuccess?: () => void
}

export function SendNotificationForm({
  broadcast = false,
  fixedUserIds = [],
  onSuccess,
}: SendNotificationFormProps) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const eventTypeOptions = Object.entries(EVENT_TYPE_LABELS).filter(
    ([value]) => (broadcast ? value === "broadcast" : value !== "broadcast"),
  )

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema) as any,
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      title: "",
      content: "",
      event_type: broadcast ? "broadcast" : "manual",
      channels: ["in_app"],
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      NotificationsService.sendAdminNotification({
        requestBody: {
          title: data.title,
          content: data.content,
          event_type: data.event_type,
          channels: data.channels,
          user_ids: fixedUserIds,
          ...(broadcast ? { broadcast: true } : {}),
        },
      }),
    onSuccess: (result) => {
      showSuccessToast(result.message)
      form.reset()
      onSuccess?.()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-notifications"] })
    },
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate(data)
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <div className="grid gap-4 py-2">
          <FormField
            control={form.control}
            name="title"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  标题 <span className="text-destructive">*</span>
                </FormLabel>
                <FormControl>
                  <Input placeholder="如：系统维护通知" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="content"
            render={({ field }) => (
              <FormItem>
                <FormLabel>内容</FormLabel>
                <FormControl>
                  <Textarea
                    className="min-h-24"
                    placeholder="通知正文"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="event_type"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  事件类型 <span className="text-destructive">*</span>
                </FormLabel>
                <FormControl>
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue placeholder="请选择事件类型" />
                    </SelectTrigger>
                    <SelectContent>
                      {eventTypeOptions.map(([value, label]) => (
                        <SelectItem key={value} value={value}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <Controller
            control={form.control}
            name="channels"
            render={({ field }) => (
              <FormItem>
                <FormLabel>
                  渠道 <span className="text-destructive">*</span>
                </FormLabel>
                <FormControl>
                  <div className="flex gap-6">
                    {Object.entries(CHANNEL_LABELS).map(([value, label]) => (
                      <label
                        key={value}
                        className="flex cursor-pointer items-center gap-2 text-sm"
                        htmlFor={value}
                      >
                        <Checkbox
                          id={value}
                          checked={field.value.includes(value)}
                          onCheckedChange={(checked) =>
                            field.onChange(
                              toggleValue(field.value, value, checked === true),
                            )
                          }
                        />
                        {label}
                      </label>
                    ))}
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              取消
            </Button>
          </DialogClose>
          <LoadingButton type="submit" loading={mutation.isPending}>
            发送
          </LoadingButton>
        </DialogFooter>
      </form>
    </Form>
  )
}
