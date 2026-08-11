import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Award, Info, Lock, Pencil, Shield } from "lucide-react"
import { type ReactNode, useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import {
  ImagesService,
  LevelsService,
  type UserPublic,
  UsersService,
} from "@/client"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
} from "@/components/ui/sidebar"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

const formSchema = z
  .object({
    email: z.email({ message: "邮箱格式不正确" }),
    username: z.string().optional(),
    full_name: z.string().optional(),
    password: z
      .string()
      .min(8, { message: "密码至少 8 个字符" })
      .optional()
      .or(z.literal("")),
    confirm_password: z.string().optional(),
    is_superuser: z.boolean().optional(),
    is_active: z.boolean().optional(),
    level_id: z.string().optional(),
    avatar_id: z.string().optional(),
  })
  .refine((data) => !data.password || data.password === data.confirm_password, {
    message: "两次输入的密码不一致",
    path: ["confirm_password"],
  })

type FormData = z.infer<typeof formSchema>

const sections = [
  { id: "basic", label: "基本信息", icon: Info },
  { id: "level-avatar", label: "等级与头像", icon: Award },
  { id: "password", label: "密码", icon: Lock },
  { id: "permissions", label: "权限", icon: Shield },
] as const

type SectionId = (typeof sections)[number]["id"]

interface EditUserProps {
  user: UserPublic
  onSuccess: () => void
}

function Section({
  id,
  activeSection,
  children,
}: {
  id: SectionId
  activeSection: SectionId
  children: ReactNode
}) {
  return (
    <div
      className={cn("flex flex-col gap-4", activeSection !== id && "md:hidden")}
    >
      {children}
    </div>
  )
}

const EditUser = ({ user, onSuccess }: EditUserProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [activeSection, setActiveSection] = useState<SectionId>("basic")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      email: user.email,
      username: user.username ?? undefined,
      full_name: user.full_name ?? undefined,
      is_superuser: user.is_superuser,
      is_active: user.is_active,
      level_id: user.level_id ?? undefined,
      avatar_id: user.avatar_id ?? "none",
    },
  })

  const { data: levels } = useQuery({
    queryKey: ["levels"],
    queryFn: () => LevelsService.readLevels(),
    enabled: isOpen,
  })

  const { data: avatarImages } = useQuery({
    queryKey: ["avatar-images"],
    queryFn: () => ImagesService.readImages({ category: "avatar", limit: 100 }),
    enabled: isOpen,
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      UsersService.updateUser({
        userId: user.id,
        requestBody: {
          email: data.email,
          username: data.username,
          full_name: data.full_name,
          is_superuser: data.is_superuser,
          is_active: data.is_active,
          password: data.password || undefined,
          level_id: data.level_id || undefined,
          avatar_id:
            data.avatar_id === "none" ? null : (data.avatar_id ?? undefined),
        },
      }),
    onSuccess: () => {
      showSuccessToast("用户更新成功")
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
    },
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate(data)
  }

  const userLabel = user.username ?? user.full_name ?? user.email

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => {
          setActiveSection("basic")
          setIsOpen(true)
        }}
      >
        <Pencil />
        编辑用户
      </DropdownMenuItem>
      <DialogContent className="overflow-hidden p-0 md:max-h-[700px] md:max-w-[800px] lg:max-w-[800px]">
        <DialogTitle className="border-b px-4 py-3 pr-10 text-base font-semibold">
          编辑用户：{userLabel}
        </DialogTitle>
        <DialogDescription className="sr-only">
          更新用户信息。
        </DialogDescription>
        <SidebarProvider className="items-start min-h-0">
          <Sidebar collapsible="none" className="hidden md:flex">
            <SidebarContent>
              <SidebarGroup>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {sections.map((section) => (
                      <SidebarMenuItem key={section.id}>
                        <SidebarMenuButton
                          isActive={activeSection === section.id}
                          onClick={() => setActiveSection(section.id)}
                        >
                          <section.icon />
                          <span>{section.label}</span>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            </SidebarContent>
          </Sidebar>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(onSubmit)}
              className="flex h-[480px] flex-1 flex-col overflow-hidden"
            >
              <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
                <Section id="basic" activeSection={activeSection}>
                  <FormField
                    control={form.control}
                    name="email"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>
                          邮箱 <span className="text-destructive">*</span>
                        </FormLabel>
                        <FormControl>
                          <Input
                            placeholder="邮箱"
                            type="email"
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
                    name="username"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>用户名</FormLabel>
                        <FormControl>
                          <Input placeholder="用户名" type="text" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="full_name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>姓名</FormLabel>
                        <FormControl>
                          <Input placeholder="姓名" type="text" {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </Section>

                <Section id="level-avatar" activeSection={activeSection}>
                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      control={form.control}
                      name="level_id"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>用户等级</FormLabel>
                          <Select
                            value={field.value ?? ""}
                            onValueChange={field.onChange}
                          >
                            <FormControl>
                              <SelectTrigger className="w-full">
                                <SelectValue placeholder="请选择等级" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {levels?.data.map((level) => (
                                <SelectItem key={level.id} value={level.id}>
                                  Lv.{level.level} - {level.name}
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
                      name="avatar_id"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>头像</FormLabel>
                          <Select
                            value={field.value ?? "none"}
                            onValueChange={field.onChange}
                          >
                            <FormControl>
                              <SelectTrigger className="w-full">
                                <SelectValue placeholder="选择头像" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              <SelectItem value="none">无头像</SelectItem>
                              {avatarImages?.data.map((image) => (
                                <SelectItem key={image.id} value={image.id}>
                                  <span className="flex items-center gap-2">
                                    <img
                                      src={image.url}
                                      alt={image.filename}
                                      className="size-6 rounded-full object-cover"
                                    />
                                    {image.filename}
                                  </span>
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </Section>

                <Section id="password" activeSection={activeSection}>
                  <FormField
                    control={form.control}
                    name="password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>设置密码</FormLabel>
                        <FormControl>
                          <Input
                            placeholder="密码"
                            type="password"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="confirm_password"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>确认密码</FormLabel>
                        <FormControl>
                          <Input
                            placeholder="密码"
                            type="password"
                            {...field}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </Section>

                <Section id="permissions" activeSection={activeSection}>
                  <FormField
                    control={form.control}
                    name="is_superuser"
                    render={({ field }) => (
                      <FormItem className="flex items-center gap-3 space-y-0">
                        <FormControl>
                          <Checkbox
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        </FormControl>
                        <FormLabel className="font-normal">
                          超级管理员？
                        </FormLabel>
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="is_active"
                    render={({ field }) => (
                      <FormItem className="flex items-center gap-3 space-y-0">
                        <FormControl>
                          <Checkbox
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        </FormControl>
                        <FormLabel className="font-normal">
                          启用账号？
                        </FormLabel>
                      </FormItem>
                    )}
                  />
                </Section>
              </div>

              <footer className="flex shrink-0 items-center justify-end gap-2 border-t p-4">
                <Button
                  type="button"
                  variant="outline"
                  disabled={mutation.isPending}
                  onClick={() => setIsOpen(false)}
                >
                  取消
                </Button>
                <LoadingButton type="submit" loading={mutation.isPending}>
                  保存
                </LoadingButton>
              </footer>
            </form>
          </Form>
        </SidebarProvider>
      </DialogContent>
    </Dialog>
  )
}

export default EditUser
