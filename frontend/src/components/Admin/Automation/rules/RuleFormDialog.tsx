import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil, Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import type { AutomationRuleCreate, AutomationRulePublic } from "@/client"
import { AutomationService } from "@/client"
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
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const formSchema = z.object({
  name: z.string().min(1, "请输入规则名称").max(128),
  description: z.string().max(500).optional(),
  event_type: z.string().min(1, "请输入事件类型").max(64),
  action_type: z.string().min(1, "请输入动作类型").max(64),
  config: z.string(),
  priority: z.coerce.number().int().min(-1000).max(1000),
  is_active: z.boolean().default(true),
})

type FormData = z.infer<typeof formSchema>

function parseConfig(value: string): Record<string, unknown> | null {
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

interface RuleFormDialogProps {
  rule?: AutomationRulePublic
  onSuccess?: () => void
}

export const RuleFormDialog = ({ rule, onSuccess }: RuleFormDialogProps) => {
  const isEdit = Boolean(rule)
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema) as any,
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      name: rule?.name ?? "",
      description: rule?.description ?? "",
      event_type: rule?.event_type ?? "",
      action_type: rule?.action_type ?? "",
      config: rule ? JSON.stringify(rule.config, null, 2) : "{}",
      priority: rule?.priority ?? 0,
      is_active: rule?.is_active ?? true,
    },
  })

  const mutation = useMutation({
    mutationFn: (data: AutomationRuleCreate) =>
      rule
        ? AutomationService.updateAutomationRule({
            id: rule.id,
            requestBody: data,
          })
        : AutomationService.createAutomationRule({ requestBody: data }),
    onSuccess: () => {
      showSuccessToast(isEdit ? "规则已更新" : "规则创建成功")
      form.reset()
      setIsOpen(false)
      onSuccess?.()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["automation-rules"] })
    },
  })

  const onSubmit = (data: FormData) => {
    const config = parseConfig(data.config)
    if (!config) {
      form.setError("config", {
        message: '必须是合法的 JSON 对象，例如 {"task_options": {}}',
      })
      return
    }
    mutation.mutate({
      name: data.name,
      description: data.description || null,
      event_type: data.event_type,
      action_type: data.action_type,
      config,
      priority: data.priority,
      is_active: data.is_active,
    })
  }

  const trigger = rule ? (
    <DropdownMenuItem
      onSelect={(e) => e.preventDefault()}
      onClick={() => setIsOpen(true)}
    >
      <Pencil />
      编辑规则
    </DropdownMenuItem>
  ) : (
    <DialogTrigger asChild>
      <Button>
        <Plus className="mr-2" />
        添加规则
      </Button>
    </DialogTrigger>
  )

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open)
        if (open && isEdit && rule) {
          form.reset({
            name: rule.name,
            description: rule.description ?? "",
            event_type: rule.event_type,
            action_type: rule.action_type,
            config: JSON.stringify(rule.config, null, 2),
            priority: rule.priority,
            is_active: rule.is_active,
          })
        }
      }}
    >
      {trigger}
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "编辑自动化规则" : "添加自动化规则"}
          </DialogTitle>
          <DialogDescription>
            配置「业务事件 → 动作」映射，事件发布后按启用规则自动生成任务。
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid gap-4 py-2">
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        规则名称 <span className="text-destructive">*</span>
                      </FormLabel>
                      <FormControl>
                        <Input
                          placeholder="如 订单支付 → 提交供应商订单"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
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
              </div>
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>规则描述</FormLabel>
                    <FormControl>
                      <Textarea
                        className="min-h-16 text-xs"
                        placeholder="规则用途说明（可选）"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-2 gap-4">
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
                  name="action_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>
                        动作类型 <span className="text-destructive">*</span>
                      </FormLabel>
                      <FormControl>
                        <Input
                          placeholder="如 submit_supplier_order"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
              <FormField
                control={form.control}
                name="config"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>配置 JSON</FormLabel>
                    <FormControl>
                      <Textarea
                        className="min-h-28 font-mono text-xs"
                        placeholder='{"task_options": {"priority": 10}}'
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="is_active"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-center gap-2">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <FormLabel className="font-normal">启用规则</FormLabel>
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
                保存
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default RuleFormDialog
