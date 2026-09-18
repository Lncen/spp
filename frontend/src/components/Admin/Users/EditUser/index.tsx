import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  Image as ImageIcon,
  Info,
  Lock,
  Medal,
  Shield,
  ShieldCheck,
  Wallet,
} from "lucide-react"
import { type ReactNode, useEffect, useState } from "react"
import { useForm } from "react-hook-form"

import {
  ImagesService,
  LevelsService,
  RolesService,
  type UserListItemPublic,
  UsersService,
  WalletsService,
} from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"
import { Form } from "@/components/ui/form"
import { LoadingButton } from "@/components/ui/loading-button"
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
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"
import { AvatarFields } from "./AvatarFields"
import { BasicInfoFields } from "./BasicInfoFields"
import { type FormData, formSchema } from "./editUserForm"
import { LevelFields } from "./LevelFields"
import { PasswordFields } from "./PasswordFields"
import { PermissionsFields } from "./PermissionsFields"
import { RoleFields } from "./RoleFields"
import { WalletPanel } from "./WalletPanel"

const sections = [
  { id: "basic", label: "基本信息", icon: Info },
  { id: "level", label: "等级", icon: Medal },
  { id: "roles", label: "角色", icon: ShieldCheck },
  { id: "wallet", label: "钱包", icon: Wallet },
  { id: "avatar", label: "头像", icon: ImageIcon },
  { id: "password", label: "密码", icon: Lock },
  { id: "permissions", label: "权限", icon: Shield },
] as const

type SectionId = (typeof sections)[number]["id"]

interface EditUserProps {
  user: UserListItemPublic
  open: boolean
  onOpenChange: (open: boolean) => void
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

const EditUser = ({ user, open, onOpenChange, onSuccess }: EditUserProps) => {
  const [activeSection, setActiveSection] = useState<SectionId>("basic")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: {
      email: "",
      username: user.username ?? undefined,
      full_name: undefined,
      is_superuser: user.is_superuser,
      is_active: user.is_active,
      can_order: undefined,
      level_id: undefined,
      avatar_id: "none",
      remark: "",
      bio: "",
    },
  })

  const { data: levels, isLoading: isLevelsLoading } = useQuery({
    queryKey: ["levels"],
    queryFn: () => LevelsService.readLevels(),
    enabled: open && activeSection === "level",
    staleTime: 5 * 60 * 1000,
  })

  const { data: avatarImages, isLoading: isAvatarImagesLoading } = useQuery({
    queryKey: ["avatar-images"],
    queryFn: () => ImagesService.readImages({ category: "avatar", limit: 100 }),
    enabled: open && activeSection === "avatar",
    staleTime: 5 * 60 * 1000,
  })

  const { data: wallet, isLoading: isWalletLoading } = useQuery({
    queryKey: ["wallet", user.id],
    queryFn: () => WalletsService.readWalletByUserId({ userId: user.id }),
    enabled: open,
  })

  const { data: detail } = useQuery({
    queryKey: ["user-detail", user.id],
    queryFn: () => UsersService.readUserById({ userId: user.id }),
    enabled: open,
  })

  // 角色目录只在打开「角色」分区时加载
  const { data: roles, isLoading: isRolesLoading } = useQuery({
    queryKey: ["roles"],
    queryFn: () => RolesService.readRoles({ limit: 100 }),
    enabled: open && activeSection === "roles",
    staleTime: 5 * 60 * 1000,
  })

  // 已分配角色需要展示在「基本信息」的标签上，打开对话框即加载
  const { data: userRoles, isLoading: isUserRolesLoading } = useQuery({
    queryKey: ["user-roles", user.id],
    queryFn: () => RolesService.readUserRoles({ userId: user.id }),
    enabled: open,
  })

  // 已分配角色不属于 PATCH /users，单独维护选中值与保存前的基线，用于比较差异
  const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([])
  const [initialRoleIds, setInitialRoleIds] = useState<string[]>([])

  useEffect(() => {
    if (!userRoles) return
    const roleIds = userRoles.data.map((role) => role.id)
    setSelectedRoleIds(roleIds)
    setInitialRoleIds(roleIds)
  }, [userRoles])

  useEffect(() => {
    if (!detail) return
    form.reset({
      email: detail.email,
      username: detail.username ?? undefined,
      full_name: detail.full_name ?? undefined,
      is_superuser: detail.is_superuser,
      is_active: detail.is_active,
      can_order: detail.can_order,
      level_id: detail.level_id ?? undefined,
      avatar_id: detail.avatar_id ?? "none",
      remark: detail.remark ?? "",
      bio: detail.bio ?? "",
    })
  }, [detail, form])

  /** 仅提交变化的角色：新增逐个分配，移除逐个解除，接口本身幂等 */
  const syncUserRoles = async () => {
    const initial = new Set(initialRoleIds)
    const next = new Set(selectedRoleIds)
    const rolesToAssign = selectedRoleIds.filter(
      (roleId) => !initial.has(roleId),
    )
    const rolesToRemove = initialRoleIds.filter((roleId) => !next.has(roleId))

    for (const roleId of rolesToAssign) {
      await RolesService.assignUserRole({
        userId: user.id,
        requestBody: { role_id: roleId },
      })
    }
    for (const roleId of rolesToRemove) {
      await RolesService.removeUserRole({ userId: user.id, roleId })
    }
  }

  const mutation = useMutation({
    mutationFn: async (data: FormData) => {
      await UsersService.updateUser({
        userId: user.id,
        requestBody: {
          email: data.email,
          username: data.username,
          full_name: data.full_name,
          is_superuser: data.is_superuser,
          is_active: data.is_active,
          can_order: data.can_order,
          password: data.password || undefined,
          level_id: data.level_id || undefined,
          avatar_id:
            data.avatar_id === "none" ? null : (data.avatar_id ?? undefined),
          remark: data.remark || null,
          bio: data.bio || null,
        },
      })
      await syncUserRoles()
    },
    onSuccess: () => {
      showSuccessToast("用户更新成功")
      setInitialRoleIds(selectedRoleIds)
      onOpenChange(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] })
      queryClient.invalidateQueries({ queryKey: ["user-roles", user.id] })
    },
  })

  const onSubmit = (data: FormData) => {
    mutation.mutate(data)
  }

  const userLabel = user.username ?? "用户"

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-hidden p-0 md:max-h-[min(800px,85svh)] md:max-w-[400px] lg:max-w-[800px]">
        <DialogTitle className="border-b px-4 py-3 pr-10 text-base font-semibold">
          编辑用户：{userLabel}
        </DialogTitle>
        <DialogDescription className="sr-only">
          更新用户信息。
        </DialogDescription>
        <SidebarProvider className="items-start min-h-0">
          <Sidebar collapsible="none" className="hidden bg-transparent md:flex">
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

          {!detail ? (
            <div className="flex h-[700px] flex-1 items-center justify-center">
              <Skeleton className="h-32 w-64" />
            </div>
          ) : (
            <Form {...form}>
              <form
                onSubmit={form.handleSubmit(onSubmit)}
                className="flex h-[700px] flex-1 flex-col overflow-hidden"
              >
                <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
                  <Section id="basic" activeSection={activeSection}>
                    <BasicInfoFields
                      avatarImages={avatarImages}
                      wallet={wallet}
                      isWalletLoading={isWalletLoading}
                      levelName={detail.level_name}
                      roles={userRoles?.data}
                    />
                  </Section>

                  <Section id="level" activeSection={activeSection}>
                    <LevelFields
                      levels={levels}
                      isLevelsLoading={isLevelsLoading}
                    />
                  </Section>

                  <Section id="roles" activeSection={activeSection}>
                    <RoleFields
                      roles={roles?.data}
                      selectedRoleIds={selectedRoleIds}
                      isLoading={isRolesLoading || isUserRolesLoading}
                      onChange={setSelectedRoleIds}
                    />
                  </Section>

                  <Section id="avatar" activeSection={activeSection}>
                    <AvatarFields
                      avatarImages={avatarImages}
                      isLoading={isAvatarImagesLoading}
                    />
                  </Section>

                  <Section id="password" activeSection={activeSection}>
                    <PasswordFields />
                  </Section>

                  <Section id="permissions" activeSection={activeSection}>
                    <PermissionsFields />
                  </Section>

                  <Section id="wallet" activeSection={activeSection}>
                    <WalletPanel
                      user={detail}
                      wallet={wallet}
                      isWalletLoading={isWalletLoading}
                    />
                  </Section>
                </div>

                <footer className="flex shrink-0 items-center justify-end gap-2 border-t p-4">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={mutation.isPending}
                    onClick={() => onOpenChange(false)}
                  >
                    取消
                  </Button>
                  <LoadingButton type="submit" loading={mutation.isPending}>
                    保存
                  </LoadingButton>
                </footer>
              </form>
            </Form>
          )}
        </SidebarProvider>
      </DialogContent>
    </Dialog>
  )
}

export default EditUser
