import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Send } from "lucide-react"
import { useState } from "react"
import { Controller, useForm } from "react-hook-form"
import { z } from "zod"

import { NotificationsService, UsersService } from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
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
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { CHANNEL_LABELS } from "./constants"

const formSchema = z.object({
  title: z.string().min(1, "请输入通知标题").max(255),
  content: z.string().max(2000),
  event_type: z.string().min(1, "请输入事件类型").max(64),
  user_ids: z.array(z.string()).min(1, "请至少选择一个接收用户"),
  channels: z.array(z.string()).min(1, "请至少选择一个渠道"),
})

type FormData = z.infer<typeof formSchema>

function toggleValue(values: string[], value: string, checked: boolean) {
  return checked ? [...values, value] : values.filter((item) => item !== value)
}

export const SendNotificationDialog = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: users } = useQuery({
    queryKey: ["admin-users"],
    queryFn: () => UsersService.readUsers({ limit: 100 }),
    enabled: isOpen,
  })

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema) as any,
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      title: "",
      content: "",
      event_type: "manual",
      user_ids: [],
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
          user_ids: data.user_ids,
          channels: data.channels,
        },
      }),
    onSuccess: (result) => {
      showSuccessToast(result.message)
      form.reset()
      setIsOpen(false)
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
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button>
          <Send className="mr-2" />
          发送通知
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>发送通知</DialogTitle>
          <DialogDescription>
            手动创建通知并异步投递，可同时选择站内与邮件渠道
          </DialogDescription>
        </DialogHeader>
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
                      <Input placeholder="如：manual" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Controller
                control={form.control}
                name="user_ids"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      接收用户 <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <div className="max-h-48 space-y-1 overflow-y-auto rounded-md border p-2">
                        {users?.data.map((user) => (
                          <label
                            key={user.id}
                            className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-accent"
                            htmlFor={user.id}
                          >
                            <Checkbox
                              id={user.id}
                              checked={field.value.includes(user.id)}
                              onCheckedChange={(checked) =>
                                field.onChange(
                                  toggleValue(
                                    field.value,
                                    user.id,
                                    checked === true,
                                  ),
                                )
                              }
                            />
                            {user.username}
                          </label>
                        ))}
                        {users?.data.length === 0 && (
                          <p className="px-1 py-2 text-xs text-muted-foreground">
                            暂无用户
                          </p>
                        )}
                      </div>
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
                        {Object.entries(CHANNEL_LABELS).map(
                          ([value, label]) => (
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
                                    toggleValue(
                                      field.value,
                                      value,
                                      checked === true,
                                    ),
                                  )
                                }
                              />
                              {label}
                            </label>
                          ),
                        )}
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
      </DialogContent>
    </Dialog>
  )
}

export default SendNotificationDialog
