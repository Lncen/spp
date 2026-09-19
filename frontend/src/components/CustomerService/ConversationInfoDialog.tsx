import { useQuery } from "@tanstack/react-query"

import {
  type ConversationPublic,
  type UserDetailPublic,
  UsersService,
} from "@/client"
import { formatDateTime } from "@/components/Admin/Automation/tasks/constants"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"

function userInfoRows(
  user: UserDetailPublic,
): { label: string; value: string }[] {
  return [
    { label: "用户名", value: user.username || "—" },
    { label: "邮箱", value: user.email || "—" },
    { label: "昵称", value: user.full_name || "—" },
    { label: "等级", value: user.level_name || "—" },
    { label: "账号状态", value: user.is_active ? "正常" : "已禁用" },
    { label: "允许下单", value: user.can_order ? "是" : "否" },
    { label: "备注", value: user.remark || "—" },
    { label: "简介", value: user.bio || "—" },
    { label: "注册时间", value: formatDateTime(user.created_at) },
    { label: "用户 ID", value: user.id },
  ]
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start gap-4">
      <span className="shrink-0 text-xs text-muted-foreground">{label}</span>
      <span className="min-w-0 flex-1 text-left text-xs wrap-anywhere">
        {value}
      </span>
    </div>
  )
}

/**
 * 用户信息弹窗：右键菜单「查看信息」打开，实时查询该会话用户的账号详情。
 * 详情接口需 `user:view` 权限，无权限时在弹窗内提示，不影响会话列表使用。
 */
export function ConversationInfoDialog({
  conversation,
  onOpenChange,
}: {
  conversation: ConversationPublic | null
  onOpenChange: (open: boolean) => void
}) {
  const userId = conversation?.user_id ?? null
  const name = conversation?.user_name ?? userId ?? "未知用户"

  const userQuery = useQuery({
    queryKey: ["user-detail", userId],
    queryFn: () => UsersService.readUserById({ userId: userId as string }),
    enabled: Boolean(userId),
    retry: false,
  })

  return (
    <Dialog open={Boolean(conversation)} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[400px]">
        <DialogHeader>
          <DialogTitle>用户信息</DialogTitle>
          <DialogDescription className="sr-only">
            当前会话对应用户的账号信息
          </DialogDescription>
        </DialogHeader>
        {/* min-w-0：避免超长邮箱把 Dialog 的网格列撑宽、内容溢出到弹窗外 */}
        {conversation ? (
          <div className="flex min-w-0 flex-col gap-4">
            <div className="flex min-w-0 items-center gap-3">
              <Avatar className="size-10 rounded-[5px]">
                <AvatarImage
                  src={conversation.user_avatar_url ?? undefined}
                  alt={name}
                />
                <AvatarFallback className="rounded-[5px] text-xs">
                  {name.slice(0, 1)}
                </AvatarFallback>
              </Avatar>
              <div className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-sm font-medium">{name}</span>
                <span className="text-xs text-muted-foreground">
                  {conversation.user_online ? "在线" : "离线"}
                </span>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              {userId === null ? (
                <p className="text-xs text-muted-foreground">
                  该会话未关联用户账号
                </p>
              ) : userQuery.isPending ? (
                Array.from({ length: 5 }).map((_, index) => (
                  <Skeleton key={index} className="h-4 w-full" />
                ))
              ) : userQuery.isError ? (
                <p className="text-xs text-muted-foreground">
                  无法获取用户信息（可能需要 user:view 权限）
                </p>
              ) : (
                userInfoRows(userQuery.data).map((row) => (
                  <InfoRow key={row.label} {...row} />
                ))
              )}
            </div>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
