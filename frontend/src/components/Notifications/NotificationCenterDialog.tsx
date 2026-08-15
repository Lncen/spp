import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { BellRing, CheckCheck, Trash2 } from "lucide-react"
import type { ReactNode } from "react"
import { useEffect, useRef, useState } from "react"

import {
  type NotificationPublic,
  type NotificationsPublic,
  NotificationsService,
  type UnreadCount,
} from "@/client"
import { formatDateTime } from "@/components/Admin/Automation/tasks/constants"
import {
  MY_NOTIFICATIONS_QUERY_KEY,
  MY_NOTIFICATIONS_UNREAD_QUERY_KEY,
} from "@/components/Notifications/constants"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

type NotificationView = "all" | "unread"

const NOTIFICATION_VIEWS: NotificationView[] = ["all", "unread"]
const PAGE_SIZE = 20
const LOAD_MORE_THRESHOLD = 100

function getMyNotificationsCountsQueryOptions() {
  return {
    queryKey: [...MY_NOTIFICATIONS_QUERY_KEY, "all"],
    queryFn: () => NotificationsService.readMyNotifications({ limit: 1 }),
  }
}

function getMyNotificationsInfiniteQueryOptions(view: NotificationView) {
  return {
    queryKey: [...MY_NOTIFICATIONS_QUERY_KEY, view, "infinite"],
    queryFn: ({ pageParam }: { pageParam: number }) =>
      NotificationsService.readMyNotifications({
        skip: pageParam,
        limit: PAGE_SIZE,
        unreadOnly: view === "unread",
      }),
    initialPageParam: 0,
    getNextPageParam: (
      lastPage: NotificationsPublic,
      allPages: NotificationsPublic[],
    ) => {
      const loaded = allPages.reduce((sum, page) => sum + page.data.length, 0)
      return loaded < lastPage.count ? loaded : undefined
    },
  }
}

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid grid-cols-[84px_1fr] gap-3">
      <span className="text-muted-foreground">{label}</span>
      <span className="break-all">{value}</span>
    </div>
  )
}

export function NotificationCenterDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [view, setView] = useState<NotificationView>("all")
  const [selected, setSelected] = useState<NotificationPublic | null>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const countsQuery = useQuery({
    ...getMyNotificationsCountsQueryOptions(),
    enabled: open,
  })
  const listQuery = useInfiniteQuery({
    ...getMyNotificationsInfiniteQueryOptions(view),
    enabled: open,
  })

  useEffect(() => {
    if (!open) {
      setView("all")
      setSelected(null)
      queryClient.invalidateQueries({
        queryKey: MY_NOTIFICATIONS_UNREAD_QUERY_KEY,
      })
    }
  }, [open, queryClient])

  const updateNotificationCache = (
    updater: (page: NotificationsPublic) => NotificationsPublic,
  ) => {
    queryClient.setQueryData<NotificationsPublic>(
      [...MY_NOTIFICATIONS_QUERY_KEY, "all"],
      (current) => (current ? updater(current) : current),
    )
    for (const item of NOTIFICATION_VIEWS) {
      queryClient.setQueryData<InfiniteData<NotificationsPublic>>(
        [...MY_NOTIFICATIONS_QUERY_KEY, item, "infinite"],
        (current) =>
          current ? { ...current, pages: current.pages.map(updater) } : current,
      )
    }
  }

  const removeFromNotificationCache = (
    notificationId: string,
    wasUnread: boolean,
  ) => {
    queryClient.setQueryData<NotificationsPublic>(
      [...MY_NOTIFICATIONS_QUERY_KEY, "all"],
      (current) =>
        current
          ? {
              ...current,
              count: Math.max(0, current.count - 1),
              unread_count: Math.max(
                0,
                current.unread_count - (wasUnread ? 1 : 0),
              ),
              data: current.data.filter((item) => item.id !== notificationId),
            }
          : current,
    )
    for (const item of NOTIFICATION_VIEWS) {
      queryClient.setQueryData<InfiniteData<NotificationsPublic>>(
        [...MY_NOTIFICATIONS_QUERY_KEY, item, "infinite"],
        (current) =>
          current
            ? {
                ...current,
                pages: current.pages.map((page) => ({
                  ...page,
                  count: Math.max(0, page.count - 1),
                  unread_count: Math.max(
                    0,
                    page.unread_count - (wasUnread ? 1 : 0),
                  ),
                  data: page.data.filter(
                    (notification) => notification.id !== notificationId,
                  ),
                })),
              }
            : current,
      )
    }
  }

  const markReadMutation = useMutation({
    mutationFn: (notificationId: string) =>
      NotificationsService.markRead({ notificationId }),
    onSuccess: (updated) => {
      updateNotificationCache((page) => ({
        ...page,
        unread_count: Math.max(
          0,
          page.unread_count - (updated.read_at ? 1 : 0),
        ),
        data: page.data.map((item) =>
          item.id === updated.id ? { ...item, read_at: updated.read_at } : item,
        ),
      }))
      setSelected((current) =>
        current && current.id === updated.id
          ? { ...current, read_at: updated.read_at }
          : current,
      )
    },
    onError: handleError.bind(showErrorToast),
  })

  const markAllReadMutation = useMutation({
    mutationFn: () => NotificationsService.markAllRead(),
    onSuccess: () => {
      const readAt = new Date().toISOString()
      updateNotificationCache((page) => ({
        ...page,
        unread_count: 0,
        data: page.data.map((item) => ({
          ...item,
          read_at: item.read_at ?? readAt,
        })),
      }))
      queryClient.setQueryData<UnreadCount>(
        MY_NOTIFICATIONS_UNREAD_QUERY_KEY,
        () => ({ unread_count: 0 }),
      )
      setSelected((current) =>
        current && !current.read_at ? { ...current, read_at: readAt } : current,
      )
      showSuccessToast("已全部标记为已读")
    },
    onError: handleError.bind(showErrorToast),
  })

  const deleteMutation = useMutation({
    mutationFn: (item: NotificationPublic) =>
      NotificationsService.deleteMyNotificationEndpoint({
        notificationId: item.id,
      }),
    onSuccess: (_message, item) => {
      removeFromNotificationCache(item.id, !item.read_at)
      setSelected(null)
      showSuccessToast("通知已删除")
    },
    onError: handleError.bind(showErrorToast),
  })

  const handleViewChange = (value: string) => {
    setView(value as NotificationView)
    setSelected(null)
    listRef.current?.scrollTo({ top: 0 })
  }

  const handleListScroll = () => {
    const el = listRef.current
    if (!el) return
    const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    if (
      distanceToBottom < LOAD_MORE_THRESHOLD &&
      listQuery.hasNextPage &&
      !listQuery.isFetchingNextPage
    ) {
      listQuery.fetchNextPage()
    }
  }

  const handleOpenItem = (item: NotificationPublic) => {
    if (!item.read_at) {
      markReadMutation.mutate(item.id)
    }
    setSelected(item)
  }

  const counts = countsQuery.data
  const notifications = listQuery.data?.pages.flatMap((page) => page.data) ?? []
  const showMarkAllRead = Boolean(counts && counts.unread_count > 0)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-hidden p-0 md:max-w-[900px]">
        <DialogTitle className="sr-only">通知</DialogTitle>
        <DialogDescription className="sr-only">查看我的通知</DialogDescription>
        <div className="flex h-[520px] flex-col">
          <header className="flex h-14 shrink-0 items-center gap-3 border-b px-4 pr-12">
            <h2 className="text-base font-semibold tracking-tight">通知</h2>
            <Tabs value={view} onValueChange={handleViewChange}>
              <TabsList className="h-auto w-auto rounded-none border-b border-border bg-transparent p-0">
                <TabsTrigger
                  value="all"
                  className="data-[state=active]:border-b-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none flex-none rounded-none border-b-2 border-transparent bg-transparent px-3 py-1.5 shadow-none"
                >
                  全部 {counts?.count ?? 0}
                </TabsTrigger>
                <TabsTrigger
                  value="unread"
                  className="data-[state=active]:border-b-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none flex-none rounded-none border-b-2 border-transparent bg-transparent px-3 py-1.5 shadow-none"
                >
                  未读 {counts?.unread_count ?? 0}
                </TabsTrigger>
              </TabsList>
            </Tabs>
            {showMarkAllRead ? (
              <Button
                variant="outline"
                size="sm"
                className="ml-auto"
                disabled={markAllReadMutation.isPending}
                onClick={() => markAllReadMutation.mutate()}
              >
                <CheckCheck data-icon="inline-start" />
                全部已读
              </Button>
            ) : null}
          </header>
          <div className="flex min-h-0 flex-1 flex-col md:flex-row">
            <div
              ref={listRef}
              onScroll={handleListScroll}
              className="flex shrink-0 flex-col gap-2 overflow-y-auto border-b p-3 md:w-80 md:border-r md:border-b-0"
            >
              <h3 className="text-sm font-medium text-muted-foreground">
                通知列表
              </h3>
              {listQuery.isPending ? (
                Array.from({ length: 5 }).map((_, index) => (
                  <Skeleton key={index} className="h-20 w-full" />
                ))
              ) : notifications.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-10 text-center">
                  <BellRing className="size-8 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">
                    {view === "unread" ? "暂无未读通知" : "暂无通知"}
                  </p>
                </div>
              ) : (
                <>
                  {notifications.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => handleOpenItem(item)}
                      className={cn(
                        "flex flex-col gap-1 rounded-lg border p-3 text-left transition-colors hover:bg-accent",
                        !item.read_at && "border-primary/30 bg-primary/5",
                        selected?.id === item.id && "bg-accent",
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={cn(
                            "truncate text-sm",
                            !item.read_at && "font-semibold",
                          )}
                        >
                          {item.title}
                        </span>
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {formatDateTime(item.created_at)}
                        </span>
                      </div>

                      {!item.read_at && (
                        <Badge variant="secondary" className="w-fit">
                          未读
                        </Badge>
                      )}
                    </button>
                  ))}
                  {listQuery.isFetchingNextPage &&
                    Array.from({ length: 2 }).map((_, index) => (
                      <Skeleton key={index} className="h-20 w-full" />
                    ))}
                </>
              )}
            </div>
            <div className="flex min-w-0 flex-1 flex-col overflow-y-auto p-4">
              <h3 className="mb-3 text-sm font-medium text-muted-foreground">
                通知信息
              </h3>
              {selected ? (
                <div className="flex flex-col gap-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex min-w-0 flex-col gap-1.5">
                      <h4 className="text-lg font-bold tracking-tight">
                        {selected.title}
                      </h4>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        {selected.read_at ? (
                          <Badge variant="outline">已读</Badge>
                        ) : (
                          <Badge variant="secondary">未读</Badge>
                        )}
                        <span>{formatDateTime(selected.created_at)}</span>
                      </div>
                    </div>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="outline"
                          size="sm"
                          className="shrink-0"
                        >
                          <Trash2 data-icon="inline-start" />
                          删除
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>删除通知</AlertDialogTitle>
                          <AlertDialogDescription>
                            确定删除「{selected.title}」吗？删除后不可恢复。
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>取消</AlertDialogCancel>
                          <AlertDialogAction
                            disabled={deleteMutation.isPending}
                            onClick={() => deleteMutation.mutate(selected)}
                          >
                            删除
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-col gap-1">
                      <span className="text-sm font-medium text-muted-foreground">
                        内容
                      </span>
                      <p className="text-sm whitespace-pre-line">
                        {selected.content || "—"}
                      </p>
                    </div>
                    <Separator />
                    <div className="flex flex-col gap-1.5 text-sm">
                      <DetailRow
                        label="通知类型"
                        value={
                          <span className="font-mono">
                            {selected.event_type}
                          </span>
                        }
                      />
                      <DetailRow
                        label="创建时间"
                        value={formatDateTime(selected.created_at)}
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
                  <BellRing className="size-8 text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">
                    选择左侧通知查看详情
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
