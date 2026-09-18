import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type RoleCreate, RolesService } from "@/client"
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
  FormDescription,
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
import { ROLES_QUERY_KEY } from "./constants"

const formSchema = z.object({
  name: z.string().min(1, "请输入角色名称").max(128),
  description: z.string().max(255).optional(),
  sort_order: z.coerce.number().int(),
})

type FormData = z.infer<typeof formSchema>

interface CreateRoleDialogProps {
  /** 创建成功回调，用于选中新角色 */
  onCreated?: (roleId: string) => void
}

export function CreateRoleDialog({ onCreated }: CreateRoleDialogProps) {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema) as any,
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: { name: "", description: "", sort_order: 0 },
  })

  const mutation = useMutation({
    mutationFn: (data: RoleCreate) =>
      RolesService.createRoleEndpoint({ requestBody: data }),
    onSuccess: (role) => {
      showSuccessToast(`角色「${role.name}」已创建`)
      form.reset()
      setIsOpen(false)
      onCreated?.(role.id)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ROLES_QUERY_KEY })
    },
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate({
      name: data.name.trim(),
      description: data.description?.trim() || null,
      sort_order: data.sort_order,
    })
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="w-full">
          <Plus data-icon="inline-start" />
          创建
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>创建角色</DialogTitle>
          <DialogDescription>
            角色码由系统自动生成，创建后可在右侧分配权限
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form
            id="create-role-form"
            onSubmit={form.handleSubmit(onSubmit)}
            className="flex flex-col gap-4"
          >
            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>角色名称</FormLabel>
                  <FormControl>
                    <Input placeholder="如：订单管理员" {...field} />
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
                    <Textarea
                      placeholder="角色职责说明"
                      {...field}
                      value={field.value ?? ""}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="sort_order"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>排序</FormLabel>
                  <FormControl>
                    <Input type="number" {...field} />
                  </FormControl>
                  <FormDescription>数值越小越靠前</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </form>
        </Form>
        <DialogFooter className="mt-4">
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              取消
            </Button>
          </DialogClose>
          <LoadingButton
            type="submit"
            form="create-role-form"
            loading={mutation.isPending}
          >
            创建
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
