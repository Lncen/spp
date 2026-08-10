import {
  createFileRoute,
  Link,
  Outlet,
  useRouterState,
} from "@tanstack/react-router"
import { Archive, Braces, ListTodo, Send } from "lucide-react"

export const Route = createFileRoute("/_layout/automation")({
  component: AutomationLayout,
})

const navItems = [
  { to: "/automation/tasks", title: "任务池", icon: ListTodo },
  { to: "/automation/archives", title: "归档", icon: Archive },
  { to: "/automation/rules", title: "规则", icon: Braces },
  { to: "/automation/events", title: "事件", icon: Send },
]

export function AutomationLayout() {
  const { location } = useRouterState()
  const pathname = location.pathname

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">自动化管理</h1>
        <p className="text-muted-foreground">
          管理自动化任务池、任务归档、事件规则与事件发布。
        </p>
      </div>
      <nav className="flex items-center gap-1 border-b">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.to)
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`inline-flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <item.icon className="size-4" />
              {item.title}
            </Link>
          )
        })}
      </nav>
      <Outlet />
    </div>
  )
}
