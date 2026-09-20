import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"
import { BellRing, CheckCheck, Trash2 } from "lucide-react"
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
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useCustomToast from "@/hooks/useCustomToast"
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

/**
 * 系统通知面板：通知列表 + 详情，嵌入客服工作台弹窗使用。
 * active 控制查询是否启用（弹窗未打开时不发请求）。
 */
export function NotificationPanel({ active }: { active: boolean }) {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [view, setView] = useState<NotificationView>("all")
  const listRef = useRef<HTMLDivElement>(null)

  const countsQuery = useQuery({
    ...getMyNotificationsCountsQueryOptions(),
    enabled: active,
  })
  const listQuery = useInfiniteQuery({
    ...getMyNotificationsInfiniteQueryOptions(view),
    enabled: active,
  })

  useEffect(() => {
    if (!active) {
      setView("all")
      queryClient.invalidateQueries({
        queryKey: MY_NOTIFICATIONS_UNREAD_QUERY_KEY,
      })
    }
  }, [active, queryClient])

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
      queryClient.invalidateQueries({
        queryKey: MY_NOTIFICATIONS_UNREAD_QUERY_KEY,
      })
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
      queryClient.invalidateQueries({
        queryKey: MY_NOTIFICATIONS_UNREAD_QUERY_KEY,
      })
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
      queryClient.invalidateQueries({
        queryKey: MY_NOTIFICATIONS_UNREAD_QUERY_KEY,
      })
      showSuccessToast("通知已删除")
    },
    onError: handleError.bind(showErrorToast),
  })

  const handleViewChange = (value: string) => {
    setView(value as NotificationView)
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
  }

  const counts = countsQuery.data
  const notifications = listQuery.data?.pages.flatMap((page) => page.data) ?? []
  const showMarkAllRead = Boolean(counts && counts.unread_count > 0)

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex h-12 shrink-0 items-center gap-3 border-b px-4 pr-12">
        <h2 className="text-base font-semibold tracking-tight">系统通知</h2>
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
      <div
        ref={listRef}
        onScroll={handleListScroll}
        className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-4"
      >
        {listQuery.isPending ? (
          Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-32 w-full" />
          ))
        ) : notifications.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 py-10 text-center">
            <BellRing className="size-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              {view === "unread" ? "暂无未读通知" : "暂无通知"}
            </p>
          </div>
        ) : (
          <>
            {notifications.map((item) => (
              <Card
                key={item.id}
                className="cursor-pointer"
                onClick={() => handleOpenItem(item)}
              >
                <CardHeader className="flex flex-row items-start justify-between gap-3">
                  <div className="flex min-w-0 flex-col gap-1">
                    <CardTitle className="text-base">
                      标题：{item.title}
                    </CardTitle>
                  </div>
                  {item.read_at ? (
                    <Badge variant="outline">已读</Badge>
                  ) : (
                    <Badge variant="secondary">未读</Badge>
                  )}
                </CardHeader>
                <CardContent className="px-4 pb-3">
                  <p className="text-sm whitespace-pre-line text-muted-foreground">
                    内容：{item.content || "—"}
                  </p>
                </CardContent>
                <CardFooter className="flex items-center justify-between gap-3 border-t ">
                  <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-muted-foreground">
                    <span>
                      通知类型：{" "}
                      <span className="font-mono">{item.event_type}</span>
                    </span>
                    <span>创建时间：{formatDateTime(item.created_at)}</span>
                  </div>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="outline" size="sm" className="shrink-0">
                        <Trash2 data-icon="inline-start" />
                        删除通知
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>删除通知</AlertDialogTitle>
                        <AlertDialogDescription>
                          确定删除「{item.title}」吗？删除后不可恢复。
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>取消</AlertDialogCancel>
                        <AlertDialogAction
                          disabled={deleteMutation.isPending}
                          onClick={() => deleteMutation.mutate(item)}
                        >
                          删除
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </CardFooter>
              </Card>
            ))}
            {listQuery.isFetchingNextPage &&
              Array.from({ length: 2 }).map((_, index) => (
                <Skeleton key={index} className="h-32 w-full" />
              ))}
          </>
        )}
      </div>
    </div>
  )
}
