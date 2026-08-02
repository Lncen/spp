import { useSuspenseQuery } from "@tanstack/react-query"
import { Suspense } from "react"

import { LevelsService } from "@/client"
import PendingLevels from "@/components/Admin/Pending/PendingLevels"
import { DataTable } from "@/components/Common/DataTable"
import { levelColumns } from "./LevelColumns"

function getLevelsQueryOptions() {
  return {
    queryFn: () => LevelsService.readLevels(),
    queryKey: ["levels"],
  }
}

function LevelsTableContent() {
  const { data: levels } = useSuspenseQuery(getLevelsQueryOptions())

  return <DataTable columns={levelColumns} data={levels.data} />
}

function LevelsTable() {
  return (
    <Suspense fallback={<PendingLevels />}>
      <LevelsTableContent />
    </Suspense>
  )
}

export const Levels = () => {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-bold tracking-tight">用户等级</h2>
        <p className="text-muted-foreground">
          等级编号固定，可编辑名称、描述与默认等级
        </p>
      </div>
      <LevelsTable />
    </div>
  )
}
