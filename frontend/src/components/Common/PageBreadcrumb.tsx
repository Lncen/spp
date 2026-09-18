import { Link as RouterLink, useRouterState } from "@tanstack/react-router"
import { Fragment } from "react"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"

const segmentTitles: Record<string, string> = {
  items: "Items",
  images: "图片",
  categories: "图片分类",
  levels: "等级",
  "product-categories": "商品分类",
  products: "商品",
  "price-templates": "价格模板",
  suppliers: "上游管理",
  schedules: "计划任务",
  automation: "自动化",
  orders: "订单",
  notifications: "通知记录",
  "global-settings": "全局设置",
  roles: "角色管理",
  admin: "用户",
  settings: "设置",
  tasks: "任务池",
  archives: "归档",
  rules: "规则",
  events: "事件",
}

export function PageBreadcrumb() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const segments = pathname.split("/").filter(Boolean)

  return (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem>
          <BreadcrumbLink asChild>
            <RouterLink to="/">主页</RouterLink>
          </BreadcrumbLink>
        </BreadcrumbItem>
        {segments.map((segment, index) => {
          const path = `/${segments.slice(0, index + 1).join("/")}`
          const title = segmentTitles[segment] ?? segment
          const isLast = index === segments.length - 1

          return (
            <Fragment key={path}>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                {isLast ? (
                  <BreadcrumbPage>{title}</BreadcrumbPage>
                ) : (
                  <BreadcrumbLink asChild>
                    <RouterLink to={path}>{title}</RouterLink>
                  </BreadcrumbLink>
                )}
              </BreadcrumbItem>
            </Fragment>
          )
        })}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
