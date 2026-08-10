import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Send } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { AutomationService } from "@/client"
import { Button } from "@/components/ui/button"
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

const formSchema = z.object({
  event_type: z.string().min(1, "请输入事件类型").max(64),
  payload: z.string(),
})

type FormData = z.infer<typeof formSchema>

function parsePayload(value: string): Record<string, unknown> | null {
  const trimmed = value.trim()
  if (!trimmed) return {}
  try {
    const parsed = JSON.parse(trimmed)
    if (
      parsed !== null &&
      typeof parsed === "object" &&
      !Array.isArray(parsed)
    ) {
      return parsed as Record<string, unknown>
    }
  } catch {
    return null
  }
  return null
}

export const PublishEventDialog = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema) as any,
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      event_type: "",
      payload: "{}",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: {
      event_type: string
      payload: Record<string, unknown>
    }) => AutomationService.publishAutomationEventRoute({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("事件已发布，启用规则将自动生成任务")
      form.reset()
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["automation-events"] })
      queryClient.invalidateQueries({ queryKey: ["automation-tasks"] })
    },
  })

  const onSubmit = (data: FormData) => {
    const payload = parsePayload(data.payload)
    if (!payload) {
      form.setError("payload", {
        message: '必须是合法的 JSON 对象，例如 {"key": "value"}',
      })
      return
    }
    mutation.mutate({ event_type: data.event_type, payload })
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button>
          <Send className="mr-2" />
          发布事件
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>发布业务事件</DialogTitle>
          <DialogDescription>
            手动发布事件并落库，启用的匹配规则将自动生成自动化任务。
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid gap-4 py-2">
              <FormField
                control={form.control}
                name="event_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      事件类型 <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="如 order.paid" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="payload"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>事件载荷 JSON</FormLabel>
                    <FormControl>
                      <Textarea
                        className="min-h-28 font-mono text-xs"
                        placeholder='{"order_id": "10001"}'
                        {...field}
                      />
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
                发布
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default PublishEventDialog
