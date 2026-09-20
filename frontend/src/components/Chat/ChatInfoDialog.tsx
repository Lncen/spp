import { useQuery } from "@tanstack/react-query"

import { ChatService } from "@/client"
import { chatParticipantsQueryKey } from "@/components/Chat/constants"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import useAuth from "@/hooks/useAuth"

/**
 * 会话信息弹窗（右键菜单「查询用户信息」）：

 * - 私聊：对方昵称、头像、在线状态与用户 ID；
 * - 群聊：群名与成员列表（昵称 / 角色 / 在线状态）。
 */
export function ChatInfoDialog({
  chatId,
  onOpenChange,
}: {
  chatId: string | null
  onOpenChange: (open: boolean) => void
}) {
  const { user: currentUser } = useAuth()
  const chatQuery = useQuery({
    queryKey: ["chat-detail", chatId],
    queryFn: () => ChatService.readChat({ chatId: chatId ?? "" }),
    enabled: Boolean(chatId),
  })
  const participantsQuery = useQuery({
    queryKey: chatParticipantsQueryKey(chatId ?? ""),
    queryFn: () => ChatService.readChatParticipants({ chatId: chatId ?? "" }),
    enabled: Boolean(chatId),
  })

  const chat = chatQuery.data
  const participants = participantsQuery.data?.data ?? []
  const isGroup = chat?.type === "GROUP"
  const counterpart = participants.find(
    (item) => item.user_id !== currentUser?.id,
  )
  const title = isGroup
    ? (chat?.name ?? "群聊")
    : (counterpart?.display_name ?? chat?.display_name ?? "用户信息")

  return (
    <Dialog open={Boolean(chatId)} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[420px]">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {isGroup ? "群聊信息" : "用户信息"}
          </DialogDescription>
        </DialogHeader>
        {chatQuery.isLoading || participantsQuery.isLoading ? (
          <Skeleton className="h-20 w-full" />
        ) : isGroup ? (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-muted-foreground">
              共 {participants.length} 位成员
            </p>
            <Separator />
            <div className="flex max-h-[360px] flex-col gap-3 overflow-y-auto">
              {participants.map((item) => (
                <div key={item.id} className="flex items-center gap-3">
                  <Avatar className="size-9 rounded-[5px]">
                    {item.display_avatar_url && (
                      <AvatarImage
                        src={item.display_avatar_url}
                        alt={item.display_name ?? "成员"}
                      />
                    )}
                    <AvatarFallback className="rounded-[5px] text-xs">
                      {(item.display_name ?? "成").slice(0, 1)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">
                      {item.display_name ?? "未知用户"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {item.is_online ? "在线" : "离线"}
                    </p>
                  </div>
                  {item.role === "OWNER" && <Badge>群主</Badge>}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <Avatar className="size-12 rounded-[5px]">
                {counterpart?.display_avatar_url && (
                  <AvatarImage
                    src={counterpart.display_avatar_url}
                    alt={title}
                  />
                )}
                <AvatarFallback className="rounded-[5px]">
                  {title.slice(0, 1)}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0">
                <p className="truncate font-medium">{title}</p>
                <p className="text-xs text-muted-foreground">
                  {counterpart?.is_online ? "在线" : "离线"}
                </p>
              </div>
            </div>
            <Separator />
            <dl className="flex flex-col gap-2 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">用户 ID</dt>
                <dd className="truncate font-mono text-xs">
                  {counterpart?.user_id ?? "-"}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-muted-foreground">会话类型</dt>
                <dd>
                  {chat?.type === "DIRECT" ? "私聊" : (chat?.type ?? "-")}
                </dd>
              </div>
            </dl>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
