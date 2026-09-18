import type { RolePublic } from "@/client"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { CreateRoleDialog } from "./CreateRoleDialog"
import { roleTypeLabel } from "./constants"

interface RoleListPanelProps {
  roles: RolePublic[]
  selectedRoleId: string | null
  onSelect: (roleId: string) => void
  onCreated: (roleId: string) => void
}

export function RoleListPanel({
  roles,
  selectedRoleId,
  onSelect,
  onCreated,
}: RoleListPanelProps) {
  return (
    <Card className="h-fit">
      <CardHeader>
        <CardTitle>角色管理</CardTitle>
        <CardDescription>共 {roles.length} 个角色</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <CreateRoleDialog onCreated={onCreated} />
        {roles.length === 0 ? (
          <p className="py-4 text-sm text-muted-foreground">
            暂无角色，点击上方「创建」新增
          </p>
        ) : (
          <div className="flex flex-col gap-1">
            {roles.map((role) => {
              const isSelected = role.id === selectedRoleId

              return (
                <button
                  key={role.id}
                  type="button"
                  onClick={() => onSelect(role.id)}
                  className={cn(
                    "flex flex-col items-start gap-1 rounded-md px-3 py-2 text-left transition-colors hover:bg-accent",
                    isSelected && "bg-accent",
                  )}
                >
                  <span className="flex w-full items-center gap-2">
                    <span className="truncate text-sm font-medium">
                      {role.name}
                    </span>
                    {role.is_active ? null : (
                      <Badge variant="secondary">已停用</Badge>
                    )}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {roleTypeLabel(role.is_system)}
                  </span>
                </button>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
