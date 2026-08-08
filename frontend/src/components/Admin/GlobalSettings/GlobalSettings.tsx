import { useSuspenseQuery } from "@tanstack/react-query"
import { Suspense } from "react"

import { SettingsService } from "@/client"
import PendingSettings from "@/components/Admin/Pending/PendingSettings"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { SettingRow } from "./SettingRow"

function getSettingsQueryOptions() {
  return {
    queryFn: () => SettingsService.readSettings(),
    queryKey: ["settings"],
  }
}

function SettingsContent() {
  const { data: settings } = useSuspenseQuery(getSettingsQueryOptions())

  return (
    <div className="flex flex-col">
      {settings.data.map((setting, index) => (
        <div key={setting.key} className="flex flex-col">
          {index > 0 && <Separator />}
          <SettingRow setting={setting} />
        </div>
      ))}
    </div>
  )
}

export const GlobalSettings = () => {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-bold tracking-tight">全局设置</h2>
        <p className="text-muted-foreground">
          运行时开关与业务参数，修改后立即生效
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>开关列表</CardTitle>
          <CardDescription>需登录查看，修改仅限超级管理员</CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense fallback={<PendingSettings />}>
            <SettingsContent />
          </Suspense>
        </CardContent>
      </Card>
    </div>
  )
}
