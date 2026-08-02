import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { PriceTemplatesService } from "@/client"
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
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const RULE_LEVELS = Array.from({ length: 10 }, (_, index) => index + 1)
const DISCOUNT_RATE_PATTERN =
  /^(10(\.0{1,4})?|0(\.\d{1,4})?|[1-9](\.\d{1,4})?)$/

const formSchema = z.object({
  name: z
    .string()
    .min(1, "模板名称不能为空")
    .max(255, "模板名称不能超过 255 个字符"),
  description: z
    .string()
    .max(255, "模板描述不能超过 255 个字符")
    .optional()
    .or(z.literal("")),
  rules: z
    .array(
      z.object({
        level: z.number(),
        discount_rate: z
          .string()
          .regex(DISCOUNT_RATE_PATTERN, "请输入 0-10 的折扣率，最多 4 位小数")
          .optional()
          .or(z.literal("")),
      }),
    )
    .length(10),
})

type FormData = z.infer<typeof formSchema>

function normalizeDiscountRate(value?: string) {
  const rate = value?.trim() || "1.5000"
  return Number(rate).toFixed(4)
}

const AddPriceTemplate = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema) as any,
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      name: "",
      description: "",
      rules: RULE_LEVELS.map((level) => ({
        level,
        discount_rate: "1.5000",
      })),
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      PriceTemplatesService.createPriceTemplate({
        requestBody: {
          name: data.name,
          description: data.description || null,
          rules: RULE_LEVELS.map((level) => {
            const rule = data.rules.find((item) => item.level === level)
            return {
              level,
              discount_rate: normalizeDiscountRate(rule?.discount_rate),
            }
          }),
        },
      }),
    onSuccess: (data) => {
      showSuccessToast(`价格模板 "${data.name}" 已创建`)
      form.reset()
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["price-templates"] })
    },
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate(data)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="my-4">
          <Plus className="mr-2" />
          添加价格模板
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>添加价格模板</DialogTitle>
          <DialogDescription>
            设置 1-10 级折扣率，实际价格 = 商品基准价 × 折扣率
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid gap-4 py-2 max-h-[60vh] overflow-y-auto pr-2">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      模板名称 <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input
                        placeholder="例如：默认价格模板"
                        type="text"
                        {...field}
                        required
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>描述</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="模板用途说明"
                        type="text"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
                {RULE_LEVELS.map((level) => (
                  <FormField
                    key={level}
                    control={form.control}
                    name={`rules.${level - 1}.discount_rate`}
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>L{level}</FormLabel>
                        <FormControl>
                          <Input
                            type="number"
                            min="0"
                            max="10"
                            step="0.0001"
                            placeholder="1.5000"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                ))}
              </div>
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  取消
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                创建
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default AddPriceTemplate
