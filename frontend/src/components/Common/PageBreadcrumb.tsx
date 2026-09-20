import { Link as RouterLink, useRouterState } from "@tanstack/react-router"
import {
  createContext,
  Fragment,
  type ReactNode,
  useContext,
  useEffect,
  useState,
} from "react"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"

const segmentTitles: Record<string, string> = {
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

interface BreadcrumbLabelContextValue {
  /** 页面追加的面包屑末级标签，null 表示不追加 */
  label: string | null
  setLabel: (label: string | null) => void
}

const BreadcrumbLabelContext = createContext<BreadcrumbLabelContextValue>({
  label: null,
  setLabel: () => {},
})

/** 为面包屑提供页面级标签状态，需包裹面包屑与页面内容 */
export function BreadcrumbLabelProvider({ children }: { children: ReactNode }) {
  const [label, setLabel] = useState<string | null>(null)

  return (
    <BreadcrumbLabelContext.Provider value={{ label, setLabel }}>
      {children}
    </BreadcrumbLabelContext.Provider>
  )
}

/** 页面用当前选中项的名称追加面包屑末级标签，卸载或标签为 null 时自动移除 */
export function useBreadcrumbLabel(label: string | null) {
  const { setLabel } = useContext(BreadcrumbLabelContext)

  useEffect(() => {
    setLabel(label)
    return () => setLabel(null)
  }, [setLabel, label])
}

export function PageBreadcrumb() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  })
  const { label } = useContext(BreadcrumbLabelContext)
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
        {label ? (
          <>
            <BreadcrumbSeparator />
            <BreadcrumbItem>
              <BreadcrumbPage>{label}</BreadcrumbPage>
            </BreadcrumbItem>
          </>
        ) : null}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
