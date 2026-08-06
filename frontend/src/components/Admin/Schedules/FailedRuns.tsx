import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query"
import type { ColumnDef } from "@tanstack/react-table"
import { History, RefreshCw } from "lucide-react"
import { Suspense, useState } from "react"

import type { ScheduleRunPublic } from "@/client"
import { SchedulesService } from "@/client"
import Pending from "@/components/Admin/Pending/PendingItems"
import { DataTable } from "@/components/Common/DataTable"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

function formatDateTime(value: string | null | undefined) {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

function getFailedRunsQueryOptions() {
  return {
    queryFn: () => SchedulesService.readFailedRuns({ skip: 0, limit: 100 }),
    queryKey: ["schedule-failed-runs"],
  }
}

function FailedRunsTable({
  onSelect,
}: {
  onSelect: (run: ScheduleRunPublic) => void
}) {
  const { data } = useSuspenseQuery(getFailedRunsQueryOptions())
  const columns: ColumnDef<ScheduleRunPublic>[] = [
    {
      accessorKey: "schedule_name",
      header: "计划名称",
      cell: ({ row }) => (
        <span className="max-w-[160px] truncate font-medium">
          {row.original.schedule_name ?? "—"}
        </span>
      ),
    },
    {
      accessorKey: "task_name",
      header: "任务",
      cell: ({ row }) => (
        <span
          className="block max-w-[220px] truncate font-mono text-xs"
          title={row.original.task_name}
        >
          {row.original.task_name}
        </span>
      ),
    },
    {
      accessorKey: "error_type",
      header: "异常类型",
      cell: ({ row }) =>
        row.original.error_type ? (
          <Badge variant="destructive">{row.original.error_type}</Badge>
        ) : (
          <span className="text-sm text-muted-foreground">—</span>
        ),
    },
    {
      accessorKey: "error_message",
      header: "错误信息",
      cell: ({ row }) => (
        <span
          className="block max-w-[240px] truncate text-sm"
          title={row.original.error_message}
        >
          {row.original.error_message}
        </span>
      ),
    },
    {
      accessorKey: "finished_at",
      header: "失败时间",
      cell: ({ row }) => (
        <span className="text-sm text-muted-foreground">
          {formatDateTime(row.original.finished_at)}
        </span>
      ),
    },
    {
      id: "detail",
      header: () => <span className="sr-only">详情</span>,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onSelect(row.original)}
          >
            详情
          </Button>
        </div>
      ),
    },
  ]
  return <DataTable columns={columns} data={data.data} />
}

const FailedRuns = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [selected, setSelected] = useState<ScheduleRunPublic | null>(null)
  const queryClient = useQueryClient()

  return (
    <>
      <Button variant="outline" onClick={() => setIsOpen(true)}>
        <History />
        失败记录
      </Button>
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-4xl">
          <DialogHeader>
            <DialogTitle>失败记录</DialogTitle>
            <DialogDescription>
              最近 100 条任务失败记录（手动执行与自动执行）。
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-end">
            <Button
              variant="ghost"
              size="sm"
              onClick={() =>
                queryClient.invalidateQueries({
                  queryKey: ["schedule-failed-runs"],
                })
              }
            >
              <RefreshCw />
              刷新
            </Button>
          </div>
          <Suspense fallback={<Pending />}>
            <FailedRunsTable onSelect={setSelected} />
          </Suspense>
        </DialogContent>
      </Dialog>
      {selected && (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open) setSelected(null)
          }}
        >
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>失败详情</DialogTitle>
              <DialogDescription>
                {selected.task_name} · {formatDateTime(selected.finished_at)}
              </DialogDescription>
            </DialogHeader>
            <div className="max-h-[60vh] overflow-auto rounded-md border bg-muted/40 p-3">
              <p className="mb-2 text-sm font-medium text-destructive">
                {selected.error_type ? `${selected.error_type}: ` : ""}
                {selected.error_message}
              </p>
              {selected.traceback ? (
                <pre className="whitespace-pre-wrap break-all font-mono text-xs">
                  {selected.traceback}
                </pre>
              ) : (
                <p className="text-sm text-muted-foreground">无堆栈信息</p>
              )}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </>
  )
}

export default FailedRuns
