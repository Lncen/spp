import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import type { TaskOption } from "@/client"
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

const formSchema = z.object({
  task_type: z.string().min(1, "请选择任务类型"),
  payload: z.string(),
  priority: z.coerce.number().int(),
  execute_at: z.string().optional(),
  max_retry: z.coerce.number().int().min(0).max(10),
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

const AddTaskDialog = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: executorOptions } = useQuery({
    queryKey: ["automation-task-options"],
    queryFn: () => AutomationService.readExecutorOptions(),
  })

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema) as any,
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      task_type: "",
      payload: "{}",
      priority: 0,
      execute_at: "",
      max_retry: 3,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: {
      task_type: string
      payload: Record<string, unknown>
      priority: number
      execute_at: string | null
      max_retry: number
    }) => AutomationService.createAutomationTask({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast("自动化任务创建成功")
      form.reset()
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
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
    mutation.mutate({
      task_type: data.task_type,
      payload,
      priority: data.priority,
      execute_at: data.execute_at ? data.execute_at : null,
      max_retry: data.max_retry,
    })
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2" />
          创建任务
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>创建自动化任务</DialogTitle>
          <DialogDescription>
            创建一次性自动化任务，由任务池扫描并交给对应 Executor 执行。
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid gap-4 py-2">
              <FormField
                control={form.control}
                name="task_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      任务类型 <span className="text-destructive">*</span>
                    </FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="选择已注册执行器" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {executorOptions?.data?.map((opt: TaskOption) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="payload"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>payload JSON</FormLabel>
                    <FormControl>
                      <Textarea
                        className="min-h-28 font-mono text-xs"
                        placeholder='{"key": "value"}'
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-3 gap-4">
                <FormField
                  control={form.control}
                  name="priority"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>优先级</FormLabel>
                      <FormControl>
                        <Input type="number" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="max_retry"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>最大重试</FormLabel>
                      <FormControl>
                        <Input type="number" min={0} max={10} {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="execute_at"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>计划执行</FormLabel>
                      <FormControl>
                        <Input type="datetime-local" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  取消
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                保存
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default AddTaskDialog
