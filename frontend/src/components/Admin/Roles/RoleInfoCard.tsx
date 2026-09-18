import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { type ReactNode, useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type RolePublic, RolesService, type RoleUpdate } from "@/client"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { ROLES_QUERY_KEY, roleTypeLabel } from "./constants"
import { DeleteRoleDialog } from "./DeleteRoleDialog"

const FORM_ID = "role-info-form"

const formSchema = z.object({
  name: z.string().min(1, "请输入角色名称").max(128),
  description: z.string().max(255).optional(),
  sort_order: z.coerce.number().int(),
  is_active: z.boolean(),
})

type FormData = z.infer<typeof formSchema>

function toFormValues(role: RolePublic): FormData {
  return {
    name: role.name,
    description: role.description ?? "",
    sort_order: role.sort_order,
    is_active: role.is_active,
  }
}

function InfoItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm">{children}</span>
    </div>
  )
}

interface RoleInfoCardProps {
  role: RolePublic
  /** 删除成功后回调，用于切换当前选中角色 */
  onDeleted: (roleId: string) => void
}

export function RoleInfoCard({ role, onDeleted }: RoleInfoCardProps) {
  /** 当前处于编辑态的角色 ID，切换角色后自动退出编辑态 */
  const [editingRoleId, setEditingRoleId] = useState<string | null>(null)
  const isEditing = editingRoleId === role.id
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema) as any,
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: toFormValues(role),
  })

  const mutation = useMutation({
    mutationFn: (data: RoleUpdate) =>
      RolesService.updateRoleEndpoint({ roleId: role.id, requestBody: data }),
    onSuccess: () => {
      showSuccessToast("角色信息已更新")
      setEditingRoleId(null)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ROLES_QUERY_KEY })
    },
  })

  const startEditing = () => {
    form.reset(toFormValues(role))
    setEditingRoleId(role.id)
  }

  const cancelEditing = () => {
    form.reset(toFormValues(role))
    setEditingRoleId(null)
  }

  const onSubmit = (data: FormData) => {
    mutation.mutate({
      name: data.name.trim(),
      description: data.description?.trim() || null,
      sort_order: data.sort_order,
      is_active: data.is_active,
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>角色信息</CardTitle>
        <CardDescription>
          角色名称、描述、排序与启停状态，与权限分配互不影响
        </CardDescription>
        <CardAction className="flex items-center gap-2">
          {isEditing ? (
            <>
              <Button
                variant="outline"
                size="sm"
                disabled={mutation.isPending}
                onClick={cancelEditing}
              >
                取消
              </Button>
              <LoadingButton
                type="submit"
                form={FORM_ID}
                size="sm"
                loading={mutation.isPending}
              >
                保存
              </LoadingButton>
            </>
          ) : (
            <>
              <DeleteRoleDialog role={role} onDeleted={onDeleted} />
              <Button size="sm" onClick={startEditing}>
                <Pencil data-icon="inline-start" />
                编辑
              </Button>
            </>
          )}
        </CardAction>
      </CardHeader>
      <CardContent>
        {isEditing ? (
          <Form {...form}>
            <form
              id={FORM_ID}
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
                      <Input {...field} />
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
                      <Textarea {...field} value={field.value ?? ""} />
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
              <FormField
                control={form.control}
                name="is_active"
                render={({ field }) => (
                  <FormItem className="flex flex-col gap-2">
                    <div className="flex items-center gap-3">
                      <FormLabel className="font-normal">启用角色</FormLabel>
                      <FormControl>
                        <Switch
                          checked={field.value}
                          disabled={role.is_system}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                    </div>
                    {role.is_system ? (
                      <FormDescription>系统内置角色不可停用</FormDescription>
                    ) : null}
                  </FormItem>
                )}
              />
            </form>
          </Form>
        ) : (
          <div className="flex flex-col gap-4">
            <InfoItem label="角色名称">{role.name}</InfoItem>
            <InfoItem label="描述">
              {role.description ? role.description : "—"}
            </InfoItem>
            <div className="flex flex-wrap items-center gap-6">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">类型</span>
                <Badge variant="secondary">
                  {roleTypeLabel(role.is_system)}
                </Badge>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">状态</span>
                <Badge variant={role.is_active ? "success" : "secondary"}>
                  {role.is_active ? "启用" : "停用"}
                </Badge>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
