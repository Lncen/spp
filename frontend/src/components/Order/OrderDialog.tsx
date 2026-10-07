import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CheckCircle2, ListChecks, XCircle } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import type {
  AdminOrdersPreviewPublic,
  AdminOrdersPublic,
  InputType,
  OrderCreate,
  ProductPublic,
} from "@/client"
import { OrdersService, ProductsService } from "@/client"
import { productStatusLabel } from "@/components/Admin/Products/constants"
import { Badge } from "@/components/ui/badge"
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
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"
import { formatAmount, randomQuantityInRange } from "@/lib/format-amount"
import { extractLinks } from "@/lib/link-extract"
import { handleError } from "@/utils"

/** 链接提取类型的 input_type（与管理员下单弹窗保持一致） */
const LINK_INPUT_TYPE = 13

/** 可下单的商品状态：在售（与后端 SALABLE_PRODUCT_STATUSES 保持一致） */
const ON_SALE_STATUS = 7

export interface OrderDialogItem {
  productId: string
  /** 默认数量（固定数量模式保存的值），打开弹窗后可修改 */
  quantity?: number
  /** 随机数量范围：打开弹窗时按商品步长取一次初始值，同样可修改 */
  randomRange?: { min: number; max: number }
}

interface OrderDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  items: OrderDialogItem[]
  onSuccess?: () => void
}

interface OrderProductEntry {
  productId: string
  product: ProductPublic | null
}

/** 统一参数槽位：按参数位置聚合组合内各商品的参数 */
interface ParamSlot {
  labels: string[]
  inputTypes: InputType[]
  required: boolean
  defaults: string[]
}

type ParamWidget = "text" | "textarea" | "number" | "password"

/**
 * 参数控件按 input_type 决定；同一位置各商品类型不一致时退化为文本输入。
 * 下拉 / 多选 / 开关等类型的选项结构由上游定义、后端不消费，因此按文本输入。
 */
function paramWidget(slot: ParamSlot): ParamWidget {
  // 混合类型：只要其中有链接提取，用多行框（链接通常一行一个粘贴）
  if (slot.inputTypes.length > 1) {
    return slot.inputTypes.includes(LINK_INPUT_TYPE) ? "textarea" : "text"
  }
  switch (slot.inputTypes[0]) {
    case 2: // 多行文本
    case 13: // 链接提取
    case 14: // ID 提取
    case 15: // 帖子 ID
      return "textarea"
    case 6: // 数字
    case 7: // 数量
      return "number"
    case 4: // 密码
      return "password"
    default:
      return "text"
  }
}

/**
 * 把组合内各商品的参数按「位置」聚合成统一输入项：
 * 第 n 个槽位对应每个商品自己的第 n 个可输入参数（各商品 key 可以不同）。
 */
function buildParamSlots(products: ProductPublic[]): ParamSlot[] {
  const slots: ParamSlot[] = []
  for (const product of products) {
    const params = (product.buy_params ?? []).filter(
      (param) => !param.use_default && !param.is_hidden,
    )
    params.forEach((param, index) => {
      const slot = slots[index] ?? {
        labels: [],
        inputTypes: [],
        required: false,
        defaults: [],
      }
      if (!slot.labels.includes(param.label)) {
        slot.labels.push(param.label)
      }
      if (!slot.inputTypes.includes(param.input_type)) {
        slot.inputTypes.push(param.input_type)
      }
      slot.required = slot.required || param.is_required
      const defaultValue = param.default_value ?? ""
      if (defaultValue && !slot.defaults.includes(defaultValue)) {
        slot.defaults.push(defaultValue)
      }
      slots[index] = slot
    })
  }
  return slots
}

/**
 * 商品不可下单的原因，空字符串表示可下单。
 * 与后端下单校验一致：仅「在售」且未关闭下单的商品允许下单。
 */
function unavailableReason(product: ProductPublic): string {
  if (product.is_closed) return "已关闭下单"
  if (product.status !== ON_SALE_STATUS)
    return productStatusLabel(product.status)
  return ""
}

/** 校验数量是否满足商品自身的购买规则 */
function validateQuantity(product: ProductPublic, quantity: number): string {
  const inventory = product.inventory
  if (!inventory) return "商品缺少库存配置"
  if (!Number.isInteger(quantity) || quantity < 1) return "数量必须是正整数"
  if (quantity < inventory.min_quantity) {
    return `数量不能小于 ${inventory.min_quantity}`
  }
  if (quantity > inventory.max_quantity) {
    return `数量不能大于 ${inventory.max_quantity}`
  }
  if (!inventory.is_batch && quantity > 1) return "该商品不支持批量购买"
  const step = Math.max(1, Number(inventory.purchase_step) || 1)
  if (quantity % step !== 0) return `数量必须是 ${step} 的整数倍`
  return ""
}

/** 下单参数摘要，用于预览与结果核对（多链接时逐单显示各自的链接） */
function paramSummary(params?: { [key: string]: unknown } | null): string {
  return Object.entries(params ?? {})
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join("，")
}

/**
 * 组合下单弹窗：数量按商品可修改（组合保存的数量只是默认值），
 * 下单参数统一填写一次并应用到组合内所有商品（按各商品自己的参数 key 提交）。
 * 走代客下单接口（跳过钱包与余额校验）：默认每个商品一张订单；
 * 链接类型参数填了多个链接时，按「链接 × 商品」逐条生成订单。
 */
export const OrderDialog = ({
  open,
  onOpenChange,
  title,
  items,
  onSuccess,
}: OrderDialogProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const productIds = items.map((item) => item.productId)

  const [quantities, setQuantities] = useState<Record<string, number>>({})
  const [paramValues, setParamValues] = useState<Record<number, string>>({})
  const [remark, setRemark] = useState("")
  const [errorMessage, setErrorMessage] = useState("")
  const [preview, setPreview] = useState<AdminOrdersPreviewPublic | null>(null)
  const [pendingOrders, setPendingOrders] = useState<OrderCreate[]>([])
  const [result, setResult] = useState<AdminOrdersPublic | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ["admin-order-dialog-products", productIds],
    queryFn: async (): Promise<OrderProductEntry[]> => {
      const settled = await Promise.allSettled(
        productIds.map((productId) =>
          ProductsService.readProduct({ productId }),
        ),
      )
      return settled.map((entry, index) => ({
        productId: productIds[index],
        product: entry.status === "fulfilled" ? entry.value : null,
      }))
    },
    enabled: open && productIds.length > 0,
  })

  useEffect(() => {
    if (open) {
      setQuantities({})
      setParamValues({})
      setRemark("")
      setErrorMessage("")
      setPreview(null)
      setPendingOrders([])
      setResult(null)
    }
  }, [open])

  // 数量初始值：固定数量用保存值，随机数量按商品步长取一次值，之后都允许手动修改
  useEffect(() => {
    if (!open || !data) return
    setQuantities((current) => {
      if (Object.keys(current).length > 0) return current
      const next: Record<string, number> = {}
      for (const item of items) {
        if (item.quantity !== undefined) {
          next[item.productId] = item.quantity
          continue
        }
        const product = data.find(
          (row) => row.productId === item.productId,
        )?.product
        const step = Math.max(
          1,
          Number(product?.inventory?.purchase_step ?? 1) || 1,
        )
        const range = item.randomRange ?? { min: 1, max: 1 }
        next[item.productId] = randomQuantityInRange(range.min, range.max, step)
      }
      return next
    })
  }, [open, data, items])

  const slots = useMemo(
    () =>
      buildParamSlots(
        (data ?? [])
          .map((entry) => entry.product)
          .filter((product): product is ProductPublic => product !== null),
      ),
    [data],
  )

  const quantityOf = (item: OrderDialogItem) =>
    quantities[item.productId] ?? item.quantity ?? item.randomRange?.min ?? 1

  const slotValue = (index: number) =>
    paramValues[index] ?? slots[index]?.defaults[0] ?? ""

  // 链接类型参数槽位：粘贴多个链接时按「链接 × 商品」拆单
  const linkSlots = slots
    .map((slot, index) => ({ slot, index }))
    .filter(({ slot }) => slot.inputTypes.includes(LINK_INPUT_TYPE))
  const linkLists = linkSlots.map(({ index }) => extractLinks(slotValue(index)))
  const linksBySlot = new Map(
    linkSlots.map((entry, position) => [entry.index, linkLists[position]]),
  )
  const batchCount = Math.max(linkLists[0]?.length ?? 0, 1)

  const buildOrders = (): { orders: OrderCreate[]; error: string } => {
    // 多个链接类型参数时，各自提取到的链接数量必须一致
    if (new Set(linkLists.map((links) => links.length)).size > 1) {
      return {
        orders: [],
        error: "各链接类型参数填写的链接数量不一致，请检查后重试",
      }
    }

    // 非在售商品不参与下单，直接拦截并列出，避免整批预览请求失败
    const blocked = (data ?? []).flatMap((entry) => {
      if (!entry.product) return []
      const reason = unavailableReason(entry.product)
      return reason ? [{ name: entry.product.name, reason }] : []
    })
    if (blocked.length > 0) {
      return {
        orders: [],
        error: `以下商品当前不可下单，请从组合中移除后重试：${blocked
          .map((row) => `${row.name}（${row.reason}）`)
          .join("、")}`,
      }
    }

    const orders: OrderCreate[] = []
    for (const item of items) {
      const product = data?.find(
        (row) => row.productId === item.productId,
      )?.product
      if (!product) {
        return { orders: [], error: "存在不可下单的商品，请刷新后重试" }
      }
      const quantity = quantityOf(item)
      const quantityError = validateQuantity(product, quantity)
      if (quantityError) {
        return { orders: [], error: `${product.name}：${quantityError}` }
      }

      for (let orderIndex = 0; orderIndex < batchCount; orderIndex += 1) {
        const params: Record<string, string> = {}
        let slotIndex = 0
        for (const param of product.buy_params ?? []) {
          if (param.use_default) continue
          if (param.is_hidden) {
            if (param.default_value) params[param.key] = param.default_value
            continue
          }
          const currentSlot = slotIndex
          slotIndex += 1
          const rawValue = slotValue(currentSlot)
          let value = rawValue
          if (param.input_type === LINK_INPUT_TYPE) {
            const links = linksBySlot.get(currentSlot) ?? []
            value = links[orderIndex] ?? ""
            if (!value && rawValue.trim() && links.length === 0) {
              return {
                orders: [],
                error: `${product.name} 的「${param.label}」未识别到链接，请粘贴 http/https 链接`,
              }
            }
          }
          if (!value) {
            if (param.is_required) {
              return {
                orders: [],
                error: `${product.name} 缺少必填参数：${param.label}`,
              }
            }
            continue
          }
          params[param.key] = value
        }
        orders.push({
          product_id: item.productId,
          quantity,
          params,
          remark: remark.trim() || null,
        })
      }
    }
    return { orders, error: "" }
  }

  const createMutation = useMutation({
    mutationFn: (orders: OrderCreate[]) =>
      OrdersService.createAdminOrdersApi({ requestBody: { orders } }),
    onSuccess: (data) => {
      setResult(data)
      showSuccessToast(
        `下单完成：成功 ${data.success_count} 单，失败 ${data.failure_count} 单`,
      )
      queryClient.invalidateQueries({ queryKey: ["orders"] })
      onSuccess?.()
    },
    onError: handleError.bind(showErrorToast),
  })

  const previewMutation = useMutation({
    mutationFn: (orders: OrderCreate[]) =>
      OrdersService.previewAdminOrdersApi({ requestBody: { orders } }),
    onSuccess: (data, orders) => {
      setPendingOrders(orders)
      setPreview(data)
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = () => {
    const { orders, error } = buildOrders()
    if (error) {
      setErrorMessage(error)
      return
    }
    setErrorMessage("")
    previewMutation.mutate(orders)
  }

  const confirmSubmit = () => {
    createMutation.mutate(pendingOrders)
    setPreview(null)
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          className="sm:max-w-2xl"
          onOpenAutoFocus={(event) => event.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>
              管理员代客下单（不扣钱包余额），数量默认取组合保存值、可修改；
              链接类型参数填多个链接时，按「链接 × 商品」逐条生成订单。
            </DialogDescription>
          </DialogHeader>
          <Separator />
          <div className="max-h-[70vh] space-y-5 overflow-y-auto pr-1">
            {isLoading && (
              <p className="text-sm text-muted-foreground">加载商品信息…</p>
            )}

            <section className="space-y-3">
              {data?.map((entry) => {
                const item = items.find(
                  (row) => row.productId === entry.productId,
                )
                if (!item) return null
                if (!entry.product) {
                  return (
                    <p
                      key={entry.productId}
                      className="text-sm text-destructive"
                    >
                      商品 {entry.productId}{" "}
                      当前不可下单，请从组合中移除后重试。
                    </p>
                  )
                }
                const product = entry.product
                const inventory = product.inventory
                const step = Math.max(
                  1,
                  Number(inventory?.purchase_step ?? 1) || 1,
                )
                const blockedReason = unavailableReason(product)
                return (
                  <div
                    key={entry.productId}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium">{product.name}</p>
                      <p className="text-xs text-muted-foreground">
                        可购 {inventory?.min_quantity ?? "—"}-
                        {inventory?.max_quantity ?? "—"}
                        {step > 1 && `，${step} 的整数倍`}
                        {(inventory?.stock ?? -1) >= 0 &&
                          `，库存 ${inventory?.stock}`}
                      </p>
                      {blockedReason && (
                        <p className="text-xs text-destructive">
                          当前不可下单
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {blockedReason && (
                        <Badge variant="destructive">{blockedReason}</Badge>
                      )}
                      {item.quantity === undefined && (
                        <Badge variant="outline">
                          随机 {item.randomRange?.min}-{item.randomRange?.max}
                        </Badge>
                      )}
                      <Label
                        htmlFor={`order-quantity-${entry.productId}`}
                        className="text-xs"
                      >
                        数量
                      </Label>
                      <Input
                        id={`order-quantity-${entry.productId}`}
                        type="number"
                        min={1}
                        step={step}
                        className="w-24"
                        disabled={blockedReason !== ""}
                        value={quantityOf(item)}
                        onChange={(event) =>
                          setQuantities((current) => ({
                            ...current,
                            [entry.productId]: Number(event.target.value),
                          }))
                        }
                      />
                      <span className="text-xs text-muted-foreground">
                        {product.fulfillment?.unit ?? "件"}
                      </span>
                    </div>
                  </div>
                )
              })}
            </section>

            {slots.length > 0 && (
              <section className="space-y-3">
                <div>
                  <h3 className="text-sm font-semibold">
                    下单参数（统一填写）
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    填一次即可，组合内所有商品都会使用这组参数，
                    提交时按各商品自己的参数键写入。
                  </p>
                </div>
                <div className="grid gap-4">
                  {slots.map((slot, index) => {
                    const widget = paramWidget(slot)
                    const label =
                      slot.labels.length === 1
                        ? slot.labels[0]
                        : `参数 ${index + 1}`
                    const inputId = `unified-param-${index}`
                    return (
                      <div key={inputId} className="grid gap-1.5">
                        <Label htmlFor={inputId}>
                          {label}
                          {slot.labels.length > 1 && (
                            <span className="text-muted-foreground">
                              （{slot.labels.join(" / ")}）
                            </span>
                          )}
                          {slot.required && (
                            <span className="text-destructive"> *</span>
                          )}
                        </Label>
                        {widget === "textarea" ? (
                          <Textarea
                            id={inputId}
                            rows={3}
                            value={slotValue(index)}
                            onChange={(event) =>
                              setParamValues((current) => ({
                                ...current,
                                [index]: event.target.value,
                              }))
                            }
                          />
                        ) : (
                          <Input
                            id={inputId}
                            type={widget}
                            value={slotValue(index)}
                            onChange={(event) =>
                              setParamValues((current) => ({
                                ...current,
                                [index]: event.target.value,
                              }))
                            }
                          />
                        )}
                        {slot.inputTypes.length > 1 && (
                          <p className="text-xs text-muted-foreground">
                            组合内各商品该参数类型不一致，按文本填写。
                          </p>
                        )}
                        {slot.inputTypes.includes(LINK_INPUT_TYPE) && (
                          <p className="text-xs text-muted-foreground">
                            链接类型参数：自动提取 http/https
                            链接，每行一个链接，多个链接会按链接拆单。
                          </p>
                        )}
                      </div>
                    )
                  })}
                </div>
                {batchCount > 1 && (
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">
                      检测到 {batchCount} 个链接：将生成 {batchCount} ×{" "}
                      {items.length} = {batchCount * items.length} 张订单。
                    </p>
                    <p className="text-xs text-muted-foreground">
                      参数不随链接变化的商品会重复提交相同参数；若该商品不支持重复下单，
                      多余订单会被拒绝并逐条显示在下单结果里。
                    </p>
                  </div>
                )}
              </section>
            )}

            <div className="grid gap-1.5">
              <Label htmlFor="order-remark">备注</Label>
              <Input
                id="order-remark"
                maxLength={255}
                placeholder="选填，将写入每张订单"
                value={remark}
                onChange={(event) => setRemark(event.target.value)}
              />
            </div>

            {errorMessage && (
              <p className="text-sm text-destructive">{errorMessage}</p>
            )}

            {result && (
              <section className="space-y-3 rounded-md border p-4">
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <span className="font-medium">共 {result.total} 单</span>
                  <Badge>成功 {result.success_count}</Badge>
                  <Badge
                    variant={
                      result.failure_count > 0 ? "destructive" : "secondary"
                    }
                  >
                    失败 {result.failure_count}
                  </Badge>
                </div>
                <div className="max-h-56 space-y-2 overflow-y-auto">
                  {result.results.map((row) => {
                    const order = pendingOrders[row.index - 1]
                    const name = data?.find(
                      (entry) => entry.productId === order?.product_id,
                    )?.product?.name
                    const summary = paramSummary(order?.params)
                    return (
                      <div
                        key={row.index}
                        className="flex items-start justify-between gap-3 rounded-md bg-muted/50 px-3 py-2 text-sm"
                      >
                        <div className="min-w-0">
                          <div className="truncate">
                            {name ?? `订单 ${row.index}`}
                            <span className="ml-2 text-muted-foreground">
                              ×{order?.quantity ?? 0}
                            </span>
                          </div>
                          {summary && (
                            <div className="truncate text-xs text-muted-foreground">
                              {summary}
                            </div>
                          )}
                        </div>
                        {row.success && row.order ? (
                          <span className="flex shrink-0 items-center gap-1.5 text-emerald-600">
                            <CheckCircle2 className="size-4 shrink-0" />
                            {formatAmount(row.order.total_amount)}
                          </span>
                        ) : (
                          <span className="flex shrink-0 items-start gap-1.5 text-destructive">
                            <XCircle className="mt-0.5 size-4 shrink-0" />
                            {row.detail || "订单创建失败"}
                          </span>
                        )}
                      </div>
                    )
                  })}
                </div>
              </section>
            )}
          </div>
          <DialogFooter>
            {result ? (
              <DialogClose asChild>
                <Button variant="outline">完成</Button>
              </DialogClose>
            ) : (
              <>
                <DialogClose asChild>
                  <Button variant="outline" disabled={createMutation.isPending}>
                    取消
                  </Button>
                </DialogClose>
                <LoadingButton
                  onClick={onSubmit}
                  loading={previewMutation.isPending}
                  disabled={isLoading || productIds.length === 0}
                >
                  <ListChecks />
                  预览并下单
                </LoadingButton>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={preview !== null}
        onOpenChange={(next) => {
          if (!next) setPreview(null)
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>确认结算金额</DialogTitle>
            <DialogDescription>{title}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            {(preview?.items ?? []).map((item) => {
              const summary = paramSummary(
                pendingOrders[item.index - 1]?.params,
              )
              return (
                <div
                  key={item.index}
                  className="flex items-start justify-between gap-4"
                >
                  <div className="min-w-0">
                    <div className="truncate">
                      {item.product_name}
                      <span className="ml-2 text-muted-foreground">
                        {formatAmount(item.unit_price)} × {item.quantity}
                      </span>
                    </div>
                    {summary && (
                      <div className="truncate text-xs text-muted-foreground">
                        {summary}
                      </div>
                    )}
                  </div>
                  <span className="shrink-0">
                    {formatAmount(item.subtotal)}
                  </span>
                </div>
              )
            })}
            <div className="flex items-center justify-between gap-4 border-t pt-3 font-medium">
              <span>合计金额</span>
              <span>{formatAmount(preview?.total_amount ?? "0")}</span>
            </div>
            <p className="text-xs text-muted-foreground">
              代客下单不扣减钱包余额，金额仅作结算记录。
            </p>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={createMutation.isPending}>
                取消
              </Button>
            </DialogClose>
            <LoadingButton
              onClick={confirmSubmit}
              loading={createMutation.isPending}
            >
              确认下单
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default OrderDialog
