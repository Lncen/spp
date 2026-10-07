import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ListChecks, X } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import type {
  ProductComboCreate,
  ProductComboItemCreate,
  ProductComboPublic,
  QuantityMode,
} from "@/client"
import { ProductCombosService, ProductFavoritesService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import {
  type ComboProductCandidate,
  ComboProductPickerDialog,
} from "./ComboProductPickerDialog"

const FIXED_MODE: QuantityMode = 1
const RANDOM_MODE: QuantityMode = 2

interface ComboItemDraft {
  productId: string
  mode: QuantityMode
  quantity: number
  minQuantity: number
  maxQuantity: number
}

interface ComboFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  combo?: ProductComboPublic | null
  initialProductIds?: string[]
}

/**
 * 组合编辑弹窗：从收藏中挑选商品，逐项设置固定数量或随机数量区间。
 */
export const ComboFormDialog = ({
  open,
  onOpenChange,
  combo,
  initialProductIds,
}: ComboFormDialogProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [name, setName] = useState("")
  const [remark, setRemark] = useState("")
  const [items, setItems] = useState<ComboItemDraft[]>([])
  const [errorMessage, setErrorMessage] = useState("")
  const [pickerOpen, setPickerOpen] = useState(false)

  const { data: favorites } = useQuery({
    queryKey: ["my-favorites"],
    queryFn: () => ProductFavoritesService.readMyFavorites({ limit: 100 }),
    enabled: open,
  })

  useEffect(() => {
    if (!open) return
    setName(combo?.name ?? "")
    setRemark(combo?.remark ?? "")
    setErrorMessage("")
    if (combo) {
      setItems(
        (combo.items ?? []).map((item) => ({
          productId: item.product_id,
          mode: item.mode,
          quantity: item.quantity ?? 1,
          minQuantity: item.min_quantity ?? 1,
          maxQuantity: item.max_quantity ?? 1,
        })),
      )
      return
    }
    setItems(
      (initialProductIds ?? []).map((productId) => ({
        productId,
        mode: FIXED_MODE,
        quantity: 1,
        minQuantity: 1,
        maxQuantity: 1,
      })),
    )
  }, [open, combo, initialProductIds])

  const candidates = useMemo(() => {
    const map = new Map<string, ComboProductCandidate>()
    for (const favorite of favorites?.data ?? []) {
      map.set(favorite.product_id, {
        id: favorite.product_id,
        name: favorite.product_name,
        imageUrl: favorite.image_url,
      })
    }
    for (const item of combo?.items ?? []) {
      if (!map.has(item.product_id)) {
        map.set(item.product_id, {
          id: item.product_id,
          name: item.product_name,
          imageUrl: item.image_url,
        })
      }
    }
    return [...map.values()]
  }, [favorites, combo])

  /** 应用选择弹窗的结果：保留已选商品的数量配置，新增商品使用默认值 */
  const applySelection = (productIds: string[]) => {
    setItems((current) => {
      const kept = current.filter((item) => productIds.includes(item.productId))
      const keptIds = new Set(kept.map((item) => item.productId))
      const added = productIds
        .filter((productId) => !keptIds.has(productId))
        .map<ComboItemDraft>((productId) => ({
          productId,
          mode: FIXED_MODE,
          quantity: 1,
          minQuantity: 1,
          maxQuantity: 1,
        }))
      return [...kept, ...added]
    })
  }

  const removeItem = (productId: string) => {
    setItems((current) =>
      current.filter((item) => item.productId !== productId),
    )
  }

  const updateItem = (productId: string, patch: Partial<ComboItemDraft>) => {
    setItems((current) =>
      current.map((item) =>
        item.productId === productId ? { ...item, ...patch } : item,
      ),
    )
  }

  const validate = (): string => {
    if (!name.trim()) return "请填写组合名称"
    if (items.length === 0) return "请至少选择一个商品"
    for (const item of items) {
      const candidate = candidates.find((row) => row.id === item.productId)
      const label = candidate?.name ?? item.productId
      if (item.mode === RANDOM_MODE) {
        if (item.minQuantity < 1 || item.maxQuantity < 1) {
          return `${label} 的最小/最大数量必须大于 0`
        }
        if (item.minQuantity > item.maxQuantity) {
          return `${label} 的最小数量不能大于最大数量`
        }
        continue
      }
      if (!Number.isInteger(item.quantity) || item.quantity < 1) {
        return `${label} 的固定数量必须是正整数`
      }
    }
    return ""
  }

  const buildPayload = (): ProductComboCreate => ({
    name: name.trim(),
    remark: remark.trim() || null,
    items: items.map<ProductComboItemCreate>((item) =>
      item.mode === RANDOM_MODE
        ? {
            product_id: item.productId,
            mode: RANDOM_MODE,
            min_quantity: item.minQuantity,
            max_quantity: item.maxQuantity,
          }
        : {
            product_id: item.productId,
            mode: FIXED_MODE,
            quantity: item.quantity,
          },
    ),
  })

  const mutation = useMutation({
    mutationFn: (payload: ProductComboCreate) =>
      combo
        ? ProductCombosService.updateMyCombo({
            comboId: combo.id,
            requestBody: payload,
          })
        : ProductCombosService.createMyCombo({ requestBody: payload }),
    onSuccess: () => {
      showSuccessToast(combo ? "组合已更新" : "组合已保存")
      queryClient.invalidateQueries({ queryKey: ["my-combos"] })
      queryClient.invalidateQueries({ queryKey: ["combo"] })
      onOpenChange(false)
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = () => {
    const error = validate()
    setErrorMessage(error)
    if (error) return
    mutation.mutate(buildPayload())
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setPickerOpen(false)
        onOpenChange(next)
      }}
    >
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{combo ? "编辑组合" : "保存组合"}</DialogTitle>
          <DialogDescription>
            组合只保存商品与数量规则，下单参数在下单时填写。
          </DialogDescription>
        </DialogHeader>
        <Separator />
        <div className="max-h-[65vh] space-y-5 overflow-y-auto pr-1">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="combo-name">
                组合名称<span className="text-destructive"> *</span>
              </Label>
              <Input
                id="combo-name"
                maxLength={50}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="combo-remark">备注</Label>
              <Input
                id="combo-remark"
                maxLength={255}
                placeholder="选填"
                value={remark}
                onChange={(event) => setRemark(event.target.value)}
              />
            </div>
          </div>

          <section className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold">已选商品</h3>
                <p className="text-xs text-muted-foreground">
                  共 {items.length} 件，来自我的收藏
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setPickerOpen(true)}
              >
                <ListChecks className="mr-1.5 size-4" />
                选择商品
              </Button>
            </div>
            {items.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                还没有选择商品，点击「选择商品」从收藏中勾选。
              </p>
            ) : (
              <div className="grid gap-3">
                {items.map((item) => {
                  const candidate = candidates.find(
                    (row) => row.id === item.productId,
                  )
                  return (
                    <div
                      key={item.productId}
                      className="grid gap-2 rounded-md border p-3"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="min-w-0 truncate text-sm font-medium">
                          {candidate?.name ?? item.productId}
                        </span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => removeItem(item.productId)}
                        >
                          <X className="mr-1.5 size-4" />
                          移除
                        </Button>
                      </div>
                      <div className="flex flex-wrap items-end gap-3">
                        <div className="grid gap-1.5">
                          <Label>数量模式</Label>
                          <Select
                            value={String(item.mode)}
                            onValueChange={(value) =>
                              updateItem(item.productId, {
                                mode: Number(value) as QuantityMode,
                              })
                            }
                          >
                            <SelectTrigger className="w-32">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value={String(FIXED_MODE)}>
                                固定数量
                              </SelectItem>
                              <SelectItem value={String(RANDOM_MODE)}>
                                随机数量
                              </SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        {item.mode === FIXED_MODE ? (
                          <div className="grid gap-1.5">
                            <Label htmlFor={`quantity-${item.productId}`}>
                              数量（下单时默认值）
                            </Label>
                            <Input
                              id={`quantity-${item.productId}`}
                              type="number"
                              min={1}
                              className="w-32"
                              value={item.quantity}
                              onChange={(event) =>
                                updateItem(item.productId, {
                                  quantity: Number(event.target.value),
                                })
                              }
                            />
                          </div>
                        ) : (
                          <>
                            <div className="grid gap-1.5">
                              <Label htmlFor={`min-${item.productId}`}>
                                最小数量
                              </Label>
                              <Input
                                id={`min-${item.productId}`}
                                type="number"
                                min={1}
                                className="w-28"
                                value={item.minQuantity}
                                onChange={(event) =>
                                  updateItem(item.productId, {
                                    minQuantity: Number(event.target.value),
                                  })
                                }
                              />
                            </div>
                            <div className="grid gap-1.5">
                              <Label htmlFor={`max-${item.productId}`}>
                                最大数量
                              </Label>
                              <Input
                                id={`max-${item.productId}`}
                                type="number"
                                min={1}
                                className="w-28"
                                value={item.maxQuantity}
                                onChange={(event) =>
                                  updateItem(item.productId, {
                                    maxQuantity: Number(event.target.value),
                                  })
                                }
                              />
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </section>

          {errorMessage && (
            <p className="text-sm text-destructive">{errorMessage}</p>
          )}
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              取消
            </Button>
          </DialogClose>
          <LoadingButton onClick={onSubmit} loading={mutation.isPending}>
            {combo ? "保存修改" : "保存组合"}
          </LoadingButton>
        </DialogFooter>
        <ComboProductPickerDialog
          open={pickerOpen}
          onOpenChange={setPickerOpen}
          candidates={candidates}
          selectedIds={items.map((item) => item.productId)}
          onConfirm={applySelection}
        />
      </DialogContent>
    </Dialog>
  )
}

export default ComboFormDialog
