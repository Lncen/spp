import { useSuspenseQuery } from "@tanstack/react-query"
import { Suspense } from "react"

import { PriceTemplatesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import AddPriceTemplate from "./AddPriceTemplate"
import PendingPriceTemplates from "./PendingPriceTemplates"
import { priceTemplateColumns } from "./PriceTemplateColumns"

function getPriceTemplatesQueryOptions() {
  return {
    queryFn: () =>
      PriceTemplatesService.readPriceTemplates({ skip: 0, limit: 100 }),
    queryKey: ["price-templates"],
  }
}

function PriceTemplatesTableContent() {
  const { data: templates } = useSuspenseQuery(getPriceTemplatesQueryOptions())

  return <DataTable columns={priceTemplateColumns} data={templates.data} />
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
