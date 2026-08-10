import { useSuspenseQuery } from "@tanstack/react-query"
import type { PaginationState } from "@tanstack/react-table"
import { Suspense, useState } from "react"

import { PriceTemplatesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import AddPriceTemplate from "./AddPriceTemplate"
import PendingPriceTemplates from "./PendingPriceTemplates"
import { priceTemplateColumns } from "./PriceTemplateColumns"

function getPriceTemplatesQueryOptions(pagination: PaginationState) {
  return {
    queryFn: () =>
      PriceTemplatesService.readPriceTemplates({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
      }),
    queryKey: ["price-templates", pagination],
  }
}

function PriceTemplatesTableContent() {
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const { data: templates } = useSuspenseQuery(
    getPriceTemplatesQueryOptions(pagination),
  )

  return (
    <DataTable
      columns={priceTemplateColumns}
      data={templates.data}
      total={templates.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function PriceTemplatesTable() {
  return (
    <Suspense fallback={<PendingPriceTemplates />}>
      <PriceTemplatesTableContent />
    </Suspense>
  )
}

export const PriceTemplates = () => {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">价格模板</h2>
          <p className="text-muted-foreground">
            管理 1-10 用户等级的价格折扣率
          </p>
        </div>
        <AddPriceTemplate />
      </div>
      <PriceTemplatesTable />
    </div>
  )
}
