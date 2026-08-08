import {
  Briefcase,
  Clock,
  FolderTree,
  Home,
  Image,
  Medal,
  Package,
  Percent,
  ReceiptText,
  Server,
  Settings,
  Tags,
  Users,
} from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = [
  { icon: Home, title: "主页", path: "/" },
  { icon: Briefcase, title: "Items", path: "/items" },
  { icon: Image, title: "图片", path: "/images" },
  { icon: Tags, title: "图片分类", path: "/categories" },
  { icon: Medal, title: "等级", path: "/levels" },
  { icon: FolderTree, title: "商品分类", path: "/product-categories" },
  { icon: Package, title: "商品", path: "/products" },
  { icon: Percent, title: "价格模板", path: "/price-templates" },
  { icon: Server, title: "上游管理", path: "/suppliers" },
  { icon: Clock, title: "计划任务", path: "/schedules" },
  { icon: ReceiptText, title: "订单", path: "/orders" },
  { icon: Settings, title: "全局设置", path: "/global-settings" },
  { icon: Users, title: "用户", path: "/admin" },
]

export function AppSidebar() {
  const { user: currentUser } = useAuth()

  const items = currentUser?.is_superuser ? [...baseItems] : baseItems

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
        <Logo variant="responsive" />
      </SidebarHeader>
      <SidebarContent>
        <Main items={items} />
      </SidebarContent>
      <SidebarFooter>
        <SidebarAppearance />
        <User user={currentUser} />
      </SidebarFooter>
    </Sidebar>
  )
}

export default AppSidebar
