import { useQuery } from "@tanstack/react-query"
import {
  Archive,
  Bell,
  CalendarClock,
  Cpu,
  Database,
  FolderTree,
  Home,
  Image,
  ListTodo,
  Medal,
  MessageSquare,
  Package,
  Percent,
  ReceiptText,
  ScrollText,
  Server,
  Settings,
  ShieldCheck,
  Tags,
  UserCog,
  Users,
  Workflow,
  Zap,
} from "lucide-react"

import { ChatService, NotificationsService } from "@/client"
import { useChat } from "@/components/Chat/ChatProvider"
import { MY_CHATS_UNREAD_QUERY_KEY } from "@/components/Chat/constants"
import { SidebarAppearance } from "@/components/Common/Appearance"
import { MY_NOTIFICATIONS_UNREAD_QUERY_KEY } from "@/components/Notifications/constants"
import { useNotifications } from "@/components/Notifications/NotificationsProvider"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import usePermissions from "@/hooks/usePermissions"
import { useRealtime } from "@/realtime/RealtimeProvider"
import { type ItemGroup, Main } from "./Main"
import { NavProjects, type Project } from "./NavProjects"
import { TeamSwitcher } from "./TeamSwitcher"
import { User } from "./User"

const navGroups: ItemGroup[] = [
  {
    label: "概览",
    items: [{ icon: Home, title: "主页", path: "/" }],
  },
  {
    label: "常用",
    path: "/automations",
    items: [
      {
        icon: ReceiptText,
        title: "订单",
        path: "/orders",
        permission: "order:view",
      },
      {
        icon: Bell,
        title: "通知记录",
        path: "/notifications",
        permission: "notification:view",
      },
    ],
  },
  {
    label: "用户",
    collapsible: true,
    items: [
      { icon: Users, title: "用户", path: "/admin", permission: "user:view" },
      {
        icon: Medal,
        title: "等级",
        path: "/levels",
        permission: "level:view",
      },
    ],
  },
  {
    label: "商品",
    collapsible: true,
    items: [
      {
        icon: Package,
        title: "商品",
        path: "/products",
        permission: "product:view",
      },
      {
        icon: FolderTree,
        title: "商品分类",
        path: "/product-categories",
        permission: "product_category:view",
      },
      {
        icon: Percent,
        title: "价格模板",
        path: "/price-templates",
        permission: "price_template:view",
      },
      {
        icon: Server,
        title: "上游管理",
        path: "/suppliers",
        permission: "supplier:view",
      },
    ],
  },
  {
    icon: Cpu,
    label: "自动化",
    collapsible: true,
    items: [
      {
        icon: ListTodo,
        title: "任务池",
        path: "/automation/tasks",
        permission: "automation_task:view",
      },
      {
        icon: Archive,
        title: "归档",
        path: "/automation/archives",
        permission: "automation_task:view",
      },
      {
        icon: Workflow,
        title: "规则",
        path: "/automation/rules",
        permission: "automation_rule:view",
      },
      {
        icon: Zap,
        title: "事件",
        path: "/automation/events",
        permission: "automation_event:view",
      },
      {
        icon: CalendarClock,
        title: "计划任务",
        path: "/schedules",
        permission: "schedule:view",
      },
    ],
  },
  {
    label: "资源",
    collapsible: true,
    items: [
      { icon: Image, title: "图片", path: "/images" },
      {
        icon: Tags,
        title: "图片分类",
        path: "/categories",
        permission: "image_category:view",
      },
    ],
  },
  {
    label: "系统",
    collapsible: true,
    items: [
      {
        icon: UserCog,
        title: "角色管理",
        path: "/roles",
        permission: "role:view",
      },
      {
        icon: ScrollText,
        title: "系统日志",
        path: "/system-logs",
        permission: "system_log:view",
      },
      {
        icon: ShieldCheck,
        title: "操作审计",
        path: "/audit-logs",
        permission: "audit_log:view",
      },
      {
        icon: Settings,
        title: "全局设置",
        path: "/global-settings",
        permission: "setting:update",
      },
      {
        icon: Database,
        title: "数据备份",
        path: "/backups",
        permission: "backup:view",
      },
    ],
  },
]

export function AppSidebar() {
  const { openNotifications } = useNotifications()
  const { openChat } = useChat()
  const { user: currentUser } = useAuth()
  const { hasPermission } = usePermissions()
  const { isConnected } = useRealtime()

  const { data: unreadData } = useQuery({
    queryKey: MY_NOTIFICATIONS_UNREAD_QUERY_KEY,
    queryFn: () => NotificationsService.readUnreadCount(),
    enabled: Boolean(currentUser),
    // 实时通道断开时兜底轮询，避免角标一直停在旧值
    refetchInterval: isConnected ? false : 60_000,
  })
  const { data: chatUnreadData } = useQuery({
    queryKey: MY_CHATS_UNREAD_QUERY_KEY,
    queryFn: () => ChatService.readMyUnreadCount(),
    enabled: Boolean(currentUser) && hasPermission("chat:self_view"),
    // 实时通道断开时兜底轮询，避免角标一直停在旧值
    refetchInterval: isConnected ? false : 60_000,
  })

  const groups = navGroups
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => !item.permission || hasPermission(item.permission),
      ),
    }))
    .filter((group) => group.items.length > 0)

  const projects: Project[] = [
    {
      name: "通知",
      icon: Bell,
      badge: unreadData?.unread_count,
      onClick: () => openNotifications(),
    },
  ]
  // 聊天入口与接口权限口径一致：持有查看自己聊天权限才展示
  if (hasPermission("chat:self_view")) {
    projects.push({
      name: "聊天",
      icon: MessageSquare,
      badge: chatUnreadData?.unread_count,
      onClick: () => openChat(),
    })
  }

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <TeamSwitcher />
      </SidebarHeader>
      <SidebarContent>
        <Main groups={groups} />
        <NavProjects projects={projects} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}

export default AppSidebar
