import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { Layers, Pencil, ShoppingCart, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"

import type { ProductComboPublic } from "@/client"
import { ProductCombosService } from "@/client"
import {
  OrderDialog,
  type OrderDialogItem,
} from "@/components/Order/OrderDialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import ComboFormDialog from "./ComboFormDialog"

const RANDOM_MODE = 2

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "—"
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: "Asia/Shanghai",
  }).format(date)
}

/**
 * 按组合明细生成下单项：固定数量直接用保存值，随机数量交给下单弹窗按商品步长取值。
 */
function buildOrderItems(combo: ProductComboPublic): OrderDialogItem[] {
  return (combo.items ?? []).map((item) =>
    item.mode === RANDOM_MODE
      ? {
          productId: item.product_id,
          randomRange: {
            min: item.min_quantity ?? 1,
            max: item.max_quantity ?? 1,
          },
        }
      : { productId: item.product_id, quantity: item.quantity ?? 1 },
  )
}

export const Combos = () => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [formOpen, setFormOpen] = useState(false)
  const [editingComboId, setEditingComboId] = useState<string | null>(null)
  const [orderComboId, setOrderComboId] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ["my-combos"],
    queryFn: () => ProductCombosService.readMyCombos({ limit: 100 }),
  })

  const { data: editingCombo } = useQuery({
    queryKey: ["combo", editingComboId],
    queryFn: () =>
      ProductCombosService.readMyCombo({ comboId: editingComboId ?? "" }),
    enabled: editingComboId !== null,
  })

  const { data: orderCombo } = useQuery({
    queryKey: ["combo", orderComboId],
    queryFn: () =>
      ProductCombosService.readMyCombo({ comboId: orderComboId ?? "" }),
    enabled: orderComboId !== null,
  })

  const orderItems = useMemo(
    () => (orderCombo ? buildOrderItems(orderCombo) : []),
    [orderCombo],
  )

  const deleteMutation = useMutation({
    mutationFn: (comboId: string) =>
      ProductCombosService.deleteMyCombo({ comboId }),
    onSuccess: () => {
      showSuccessToast("组合已删除")
      queryClient.invalidateQueries({ queryKey: ["my-combos"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const combos = data?.data ?? []

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight">我的组合</h2>
          <p className="text-muted-foreground">
            保存好的商品组合可以一键下单，随机数量的组合每次下单都会重新取值
          </p>
        </div>
        <Button
          onClick={() => {
            setEditingComboId(null)
            setFormOpen(true)
          }}
        >
          <Layers className="mr-2 size-4" />
          新建组合
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">加载组合…</p>
      ) : combos.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <Layers className="size-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              还没有组合，先在收藏夹里勾选商品保存为组合吧。
            </p>
            <Button asChild variant="outline">
              <Link to="/favorites">去我的收藏</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
          {combos.map((combo) => (
            <Card key={combo.id}>
              <CardContent className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{combo.name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {combo.remark || "无备注"}
                    </p>
                  </div>
                  <Badge variant="secondary">{combo.item_count} 件商品</Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  更新时间：{formatDateTime(combo.updated_at)}
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    size="sm"
                    disabled={combo.item_count === 0}
                    title={
                      combo.item_count === 0
                        ? "组合内没有可用商品，请先编辑组合"
                        : undefined
                    }
                    onClick={() => setOrderComboId(combo.id)}
                  >
                    <ShoppingCart className="mr-1.5 size-4" />
                    组合下单
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setEditingComboId(combo.id)
                      setFormOpen(true)
                    }}
                  >
                    <Pencil className="mr-1.5 size-4" />
                    编辑
                  </Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button size="sm" variant="ghost">
                        <Trash2 className="mr-1.5 size-4" />
                        删除
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>删除组合</AlertDialogTitle>
                        <AlertDialogDescription>
                          确定要删除组合 <strong>{combo.name}</strong>{" "}
                          吗？此操作不可撤销。
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>取消</AlertDialogCancel>
                        <AlertDialogAction
                          onClick={() => deleteMutation.mutate(combo.id)}
                        >
                          删除
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <ComboFormDialog
        open={
          formOpen && (editingComboId === null || editingCombo !== undefined)
        }
        onOpenChange={(open) => {
          setFormOpen(open)
          if (!open) setEditingComboId(null)
        }}
        combo={editingComboId ? (editingCombo ?? null) : null}
      />

      <OrderDialog
        open={orderItems.length > 0}
        onOpenChange={(open) => {
          if (!open) setOrderComboId(null)
        }}
        title={orderCombo ? `组合下单：${orderCombo.name}` : "组合下单"}
        items={orderItems}
      />
    </div>
  )
}

export default Combos
