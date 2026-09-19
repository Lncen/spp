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
  MessagesSquare,
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

import { NotificationsService } from "@/client"
import { SidebarAppearance } from "@/components/Common/Appearance"
import { useCustomerService } from "@/components/CustomerService/CustomerServiceProvider"
import { MY_UNREAD_SUMMARY_QUERY_KEY } from "@/components/Notifications/constants"
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
  const { openCustomerService } = useCustomerService()
  const { openNotifications } = useNotifications()
  const { user: currentUser } = useAuth()
  const { hasPermission } = usePermissions()

  const { data: unreadData } = useQuery({
    queryKey: MY_UNREAD_SUMMARY_QUERY_KEY,
    queryFn: () => NotificationsService.readUnreadSummary(),
    enabled: Boolean(currentUser),
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
      badge: unreadData?.notification_unread_count,
      onClick: () => openNotifications(),
    },
    {
      name: "会话",
      icon: MessagesSquare,
      badge: unreadData?.conversation_unread_count,
      onClick: () => openCustomerService(),
    },
  ]

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
