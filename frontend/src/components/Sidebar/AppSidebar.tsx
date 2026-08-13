import {
  Briefcase,
  Cpu,
  FolderTree,
  Frame,
  Home,
  Image,
  Map as MapIcon,
  Medal,
  Package,
  Percent,
  PieChart,
  ReceiptText,
  Server,
  Settings,
  Tags,
  Users,
  CalendarClock,
  ListTodo,
  Archive,
  Workflow,
  Zap,
} from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
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
      { icon: ReceiptText, title: "订单", path: "/orders" },


    ],
  },
  {
    label: "用户",
    collapsible: true,
    items: [
      { icon: Users, title: "用户", path: "/admin", superuserOnly: true },
      { icon: Medal, title: "等级", path: "/levels", superuserOnly: true },
    ],
  },
  {
    label: "商品",
    collapsible: true,
    items: [
      { icon: Package, title: "商品", path: "/products" },
      { icon: FolderTree, title: "商品分类", path: "/product-categories" },
      { icon: Percent, title: "价格模板", path: "/price-templates" },
      { icon: Server, title: "上游管理", path: "/suppliers" },
    ],
  },
  {
    icon: Cpu,
    label: "自动化",
    collapsible: true,
    items: [
      { icon: ListTodo, title: "任务池", path: "/automation/tasks" },
      { icon: Archive, title: "归档", path: "/automation/archives" },
      { icon: Workflow, title: "规则", path: "/automation/rules" },
      { icon: Zap, title: "事件", path: "/automation/events" },
      { icon: CalendarClock, title: "计划任务", path: "/schedules" },
    ],
  },
  {
    label: "资源",
    collapsible: true,
    items: [
      { icon: Briefcase, title: "Items", path: "/items" },
      { icon: Image, title: "图片", path: "/images" },
      { icon: Tags, title: "图片分类", path: "/categories" },
    ],
  },
  {
    label: "系统",
    collapsible: true,
    items: [
      {
        icon: Settings,
        title: "全局设置",
        path: "/global-settings",
        superuserOnly: true,
      },
    ],
  },
]

// 示例数据，替换为真实项目即可
const projects: Project[] = [
  { name: "设计工程", url: "#", icon: Frame },
  { name: "销售与营销", url: "#", icon: PieChart },
  { name: "旅行", url: "#", icon: MapIcon },
]

export function AppSidebar() {
  const { user: currentUser } = useAuth()
  const isSuperuser = currentUser?.is_superuser ?? false

  const groups = isSuperuser ? navGroups : []

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
