import { useSuspenseQuery } from "@tanstack/react-query"
import type { PaginationState } from "@tanstack/react-table"
import { Suspense, useState } from "react"

import { AutomationService } from "@/client"
import Pending from "@/components/Admin/Pending/PendingItems"
import { DataTable } from "@/components/Common/DataTable"
import { ruleColumns } from "./columns"
import RuleFormDialog from "./RuleFormDialog"

function getRulesQueryOptions(pagination: PaginationState) {
  return {
    queryFn: () =>
      AutomationService.readAutomationRules({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
      }),
    queryKey: ["automation-rules", pagination],
  }
}

function RulesTableContent() {
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const { data: rules } = useSuspenseQuery(getRulesQueryOptions(pagination))
  return (
    <DataTable
      columns={ruleColumns}
      data={rules.data}
      total={rules.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function RulesTable() {
  return (
    <Suspense fallback={<Pending />}>
      <RulesTableContent />
    </Suspense>
  )
}

export function RulesSection() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">自动化规则</h2>
          <p className="text-sm text-muted-foreground">
            配置「业务事件 → 动作」映射，启用后事件发布将自动生成任务。
          </p>
        </div>
        <RuleFormDialog />
      </div>
      <RulesTable />
    </div>
  )
}
