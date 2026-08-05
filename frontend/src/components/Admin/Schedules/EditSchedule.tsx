import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import type { SchedulePublic, ScheduleUpdate } from "@/client"
import { SchedulesService } from "@/client"
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
} from "@/components/ui/dialog"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
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
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const SCHEDULE_TYPE_OPTIONS = [
  { value: "crontab", label: "定时执行（crontab）" },
  { value: "interval", label: "间隔执行（interval）" },
]

const PERIOD_OPTIONS = [
  { value: "days", label: "天" },
  { value: "hours", label: "小时" },
  { value: "minutes", label: "分钟" },
  { value: "seconds", label: "秒" },
  { value: "microseconds", label: "微秒" },
]

const formSchema = z.object({
  name: z.string().min(1, "请输入计划名称").max(255),
  task: z.string().min(1, "请选择任务"),
  schedule_type: z.enum(["crontab", "interval"] as const),
  crontab: z.object({
    minute: z.string().min(1).max(240),
    hour: z.string().min(1).max(96),
    day_of_week: z.string().min(1).max(64),
    day_of_month: z.string().min(1).max(124),
    month_of_year: z.string().min(1).max(124),
    timezone: z.string().min(1).max(64),
  }),
  interval: z.object({
    every: z.coerce.number().int().min(1, "间隔必须大于 0"),
    period: z.enum([
      "days",
      "hours",
      "minutes",
      "seconds",
      "microseconds",
    ] as const),
  }),
  args: z.string(),
  kwargs: z.string(),
  enabled: z.boolean().default(true),
  description: z.string().max(1024).optional().or(z.literal("")),
})

type FormData = z.infer<typeof formSchema>

function parseJsonField(value: string, expected: "array"): unknown[] | null
function parseJsonField(
  value: string,
  expected: "object",
): Record<string, unknown> | null
function parseJsonField(
  value: string,
  expected: "array" | "object",
): unknown[] | Record<string, unknown> | null {
  const trimmed = value.trim()
  if (!trimmed) {
    return expected === "array" ? [] : {}
  }
  try {
    const parsed = JSON.parse(trimmed)
    if (expected === "array" && Array.isArray(parsed)) {
      return parsed as unknown[]
    }
    if (
      expected === "object" &&
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

interface EditScheduleProps {
  schedule: SchedulePublic
  onSuccess: () => void
}

const EditSchedule = ({ schedule, onSuccess }: EditScheduleProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { data: taskOptions } = useQuery({
    queryKey: ["schedule-task-options"],
    queryFn: () => SchedulesService.readTaskOptions(),
  })

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema) as any,
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      name: schedule.name,
      task: schedule.task,
      schedule_type: schedule.schedule_type,
      crontab: {
        minute: schedule.crontab?.minute ?? "*",
        hour: schedule.crontab?.hour ?? "*",
        day_of_week: schedule.crontab?.day_of_week ?? "*",
        day_of_month: schedule.crontab?.day_of_month ?? "*",
        month_of_year: schedule.crontab?.month_of_year ?? "*",
        timezone: schedule.crontab?.timezone ?? "Asia/Shanghai",
      },
      interval: {
        every: schedule.interval?.every ?? 30,
        period: schedule.interval?.period ?? "minutes",
      },
      args: JSON.stringify(schedule.args ?? []),
      kwargs: JSON.stringify(schedule.kwargs ?? {}),
      enabled: schedule.enabled,
      description: schedule.description ?? "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: ScheduleUpdate) =>
      SchedulesService.updateSchedule({
        id: schedule.id,
        requestBody: data,
      }),
    onSuccess: () => {
      showSuccessToast("计划任务更新成功")
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] })
    },
  })

  const onSubmit = (data: FormData) => {
    const args = parseJsonField(data.args, "array")
    const kwargs = parseJsonField(data.kwargs, "object")
    if (!args) {
      form.setError("args", {
        message: "必须是合法的 JSON 数组，例如 [\"a\", 1]",
      })
      return
    }
    if (!kwargs) {
      form.setError("kwargs", {
        message: "必须是合法的 JSON 对象，例如 {\"key\": \"value\"}",
      })
      return
    }

    mutation.mutate({
      name: data.name,
      task: data.task,
      schedule_type: data.schedule_type,
      crontab:
        data.schedule_type === "crontab" ? data.crontab : undefined,
      interval:
        data.schedule_type === "interval" ? data.interval : undefined,
      args,
      kwargs,
      enabled: data.enabled,
      description: data.description || undefined,
    })
  }

  const scheduleType = form.watch("schedule_type")

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Pencil />
        编辑计划任务
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>编辑计划任务</DialogTitle>
          <DialogDescription>
            更新调度规则与参数；切换调度类型时需要填写对应配置。
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid gap-4 py-2 max-h-[65vh] overflow-y-auto pr-2">
              <FormField
                control={form.control}
                name="enabled"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center gap-4 text-base">
                    <FormControl>
                      <Checkbox 
                        checked={field.value} 
                        onCheckedChange={field.onChange}  
                        className="h-5 w-5"
                      />
                    </FormControl>
                    <FormLabel className="font-normal text-base">启用</FormLabel>
                    <FormMessage />
                  </FormItem>
                )}
              />
            <div className="grid grid-cols-2 gap-4">
              {/* 第一列：计划名称 - 占 3/6 = 1/2 */}
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem className="col-span-1">
                    <FormLabel>计划名称</FormLabel>
                    <FormControl>
                      <Input {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              
              {/* 第二列：调度类型 - 占 2/6 = 1/3 */}
              <FormField
                control={form.control}
                name="schedule_type"
                render={({ field }) => (
                  <FormItem className="col-span-1">
                    <FormLabel>调度类型</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {SCHEDULE_TYPE_OPTIONS.map((opt) => (
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
            </div>

              <FormField
                control={form.control}
                name="task"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>任务</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger  className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {taskOptions?.data?.map((opt) => (
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

              {scheduleType === "crontab" ? (
                <div className="grid grid-cols-5 gap-4">
                  <FormField
                    control={form.control}
                    name="crontab.month_of_year"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>月</FormLabel>
                        <FormControl>
                          <Input placeholder="*" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="crontab.day_of_week"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>星期</FormLabel>
                        <FormControl>
                          <Input placeholder="*" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="crontab.day_of_month"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>日</FormLabel>
                        <FormControl>
                          <Input placeholder="*" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="crontab.hour"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>小时</FormLabel>
                        <FormControl>
                          <Input placeholder="*" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="crontab.minute"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>分钟</FormLabel>
                        <FormControl>
                          <Input placeholder="*" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
 
 
   
 
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="interval.every"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>间隔</FormLabel>
                        <FormControl>
                          <Input type="number" min={1} {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                  <FormField
                    control={form.control}
                    name="interval.period"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>单位</FormLabel>
                        <Select
                          onValueChange={field.onChange}
                          value={field.value}
                        >
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {PERIOD_OPTIONS.map((opt) => (
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
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="args"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>args JSON</FormLabel>
                      <FormControl>
                        <Input placeholder='["param1", 1]' {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="kwargs"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>kwargs JSON</FormLabel>
                      <FormControl>
                        <Input placeholder='{"key": "value"}' {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid grid-cols-1 gap-4">
   
                <FormField
                  control={form.control}
                  name="description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>描述</FormLabel>
                      <FormControl>
                        <Input placeholder="备注说明（可选）" {...field}/>
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

export default EditSchedule
