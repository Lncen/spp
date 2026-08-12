import { Link as RouterLink, useRouterState } from "@tanstack/react-router"
import { ChevronRight, type LucideIcon } from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  useSidebar,
} from "@/components/ui/sidebar"

export type Item = {
  icon: LucideIcon
  title: string
  path: string
  /** 子菜单项，存在时渲染为可展开的父级菜单 */
  items?: { title: string; path: string }[]
  /** 仅超级管理员可见 */
  superuserOnly?: boolean
}

export type ItemGroup = {
  label: string
  /** 分组标题图标，可选 */
  icon?: LucideIcon
  path?: string
  items: Item[]
  /** 分组标题可点击折叠 */
  collapsible?: boolean
}

interface MainProps {
  groups: ItemGroup[]
}

export function Main({ groups }: MainProps) {
  const { isMobile, setOpenMobile } = useSidebar()
  const router = useRouterState()
  const currentPath = router.location.pathname

  const handleMenuClick = () => {
    if (isMobile) {
      setOpenMobile(false)
    }
  }

  return (
    <>
      {groups.map((group) => {
        const menu = (
          <SidebarGroupContent>
            <SidebarMenu>
              {group.items.map((item) => {
                if (item.items?.length) {
                  const isActive = currentPath.startsWith(item.path)

                  return (
                    <Collapsible
                      key={item.title}
                      defaultOpen={isActive}
                      className="group/collapsible"
                    >
                      <SidebarMenuItem>
                        <CollapsibleTrigger asChild>
                          <SidebarMenuButton
                            tooltip={item.title}
                            isActive={isActive}
                          >
                            <item.icon />
                            <span>{item.title}</span>
                            <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                          </SidebarMenuButton>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                          <SidebarMenuSub>
                            {item.items.map((subItem) => {
                              const isSubActive = currentPath === subItem.path

                              return (
                                <SidebarMenuSubItem key={subItem.title}>
                                  <SidebarMenuSubButton
                                    asChild
                                    isActive={isSubActive}
                                  >
                                    <RouterLink
                                      to={subItem.path}
                                      onClick={handleMenuClick}
                                    >
                                      <span>{subItem.title}</span>
                                    </RouterLink>
                                  </SidebarMenuSubButton>
                                </SidebarMenuSubItem>
                              )
                            })}
                          </SidebarMenuSub>
                        </CollapsibleContent>
                      </SidebarMenuItem>
                    </Collapsible>
                  )
                }

                const isActive = currentPath === item.path

                return (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      tooltip={item.title}
                      isActive={isActive}
                      asChild
                    >
                      <RouterLink to={item.path} onClick={handleMenuClick}>
                        <item.icon />
                        <span>{item.title}</span>
                      </RouterLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        )

        return (
          <SidebarGroup key={group.label}>
            {group.collapsible ? (
              <Collapsible className="group/collapsible-group">
                <SidebarGroupLabel asChild>
                  <CollapsibleTrigger className="w-full">
                    {group.icon ? <group.icon /> : null}
                    <span>{group.label}</span>
                    <ChevronRight className="ml-auto transition-transform duration-200 group-data-[state=open]/collapsible-group:rotate-90" />
                  </CollapsibleTrigger>
                </SidebarGroupLabel>
                <CollapsibleContent>{menu}</CollapsibleContent>
              </Collapsible>
            ) : (
              <>
                <SidebarGroupLabel>
                  {group.icon ? <group.icon /> : null}
                  {group.label}
                </SidebarGroupLabel>
                {menu}
              </>
            )}
          </SidebarGroup>
        )
      })}
    </>
  )
}
