import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import type { SupplierPublic } from "@/client"
import type { PlatformOption, SupplierUpdate } from "@/client"
import { SuppliersService } from "@/client"
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

const STATUS_OPTIONS = [
  { value: "active", label: "启用" },
  { value: "inactive", label: "停用" },
  { value: "suspended", label: "冻结" },
]
const CONNECTION_OPTIONS = [
  { value: "online", label: "在线" },
  { value: "offline", label: "离线" },
  { value: "unknown", label: "未知" },
]

const formSchema = z.object({
  platform: z.string().min(1, "请选择平台").optional(),
  name: z.string().min(1, "请输入供应商名称").max(255).optional(),
  base_url: z.string().min(1, "请输入 API 地址").max(512).optional(),
  app_key: z.string().min(1, "请输入应用 Key").max(512).optional(),
  app_secret: z.string().max(512).optional().or(z.literal("")),
  status: z.string().optional(),
  connection_status: z.string().optional(),
  timeout_seconds: z.coerce.number().int().min(1).max(300).optional(),
  retry_times: z.coerce.number().int().min(0).max(10).optional(),
  description: z.string().max(1024).optional().or(z.literal("")),
})

type FormData = z.infer<typeof formSchema>

interface EditSupplierProps {
  supplier: SupplierPublic
  onSuccess: () => void
}

const EditSupplier = ({ supplier, onSuccess }: EditSupplierProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { data: platformOptions } = useQuery({
    queryKey: ["platform-options"],
    queryFn: () => SuppliersService.getPlatformOptions(),
  })
  const { showSuccessToast, showErrorToast } = useCustomToast()

const form = useForm<FormData>({
    resolver: zodResolver(formSchema) as any,
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      platform: supplier.platform,
      name: supplier.name,
      base_url: supplier.base_url,
      app_key: supplier.app_key,
      app_secret: "",
      status: supplier.status,
      connection_status: supplier.connection_status,
      timeout_seconds: supplier.timeout_seconds,
      retry_times: supplier.retry_times,
      description: supplier.description ?? "",
    },
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      SuppliersService.updateSupplier({
        id: supplier.id,
        requestBody: data as SupplierUpdate,
      }),
    onSuccess: () => {
      showSuccessToast("供应商更新成功")
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["suppliers"] })
    },
  })

  const onSubmit = (data: FormData) => {
    // Remove empty app_secret so it's not sent
    const submitData = { ...data }
    if (!submitData.app_secret) {
      delete submitData.app_secret
    }
    mutation.mutate(submitData)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Pencil />
        编辑供应商
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>编辑供应商</DialogTitle>
          <DialogDescription>
            更新供应商信息。App Secret 留空则保持原值。
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid gap-4 py-2 max-h-[60vh] overflow-y-auto pr-2">
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>名称</FormLabel>
                      <FormControl>
                        <Input placeholder="例如：OpenAI 生产" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="platform"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>平台</FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="选择平台" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {platformOptions?.data?.map((opt: PlatformOption) => (
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
                name="base_url"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>接口地址</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="https://api.openai.com/v1"
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
                  name="app_key"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>应用 Key</FormLabel>
                      <FormControl>
                        <Input placeholder="API Key" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="app_secret"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>应用 Secret</FormLabel>
                      <FormControl>
                        <Input
                          type="password"
                        placeholder="留空则保持原值"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <FormField
                  control={form.control}
                  name="status"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>状态</FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {STATUS_OPTIONS.map((opt) => (
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
                  name="connection_status"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>连接</FormLabel>
                      <Select
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {CONNECTION_OPTIONS.map((opt) => (
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
                  name="timeout_seconds"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>超时（秒）</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={1}
                          max={300}
                          placeholder="30"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="retry_times"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>重试次数</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={0}
                          max={10}
                          placeholder="3"
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
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>备注</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="备注说明（可选）"
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
                保存
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default EditSupplier
