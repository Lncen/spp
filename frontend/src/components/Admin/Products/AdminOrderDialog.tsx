import { useMutation, useQueryClient } from "@tanstack/react-query"
import { CheckCircle2, ListChecks, ShoppingCart, XCircle } from "lucide-react"
import { useState } from "react"

import type {
  AdminOrdersPublic,
  OrderCreate,
  ProductBuyParamPublic,
  ProductPublic,
} from "@/client"
import { OrdersService } from "@/client"
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
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

type OrderMode = "normal" | "batch" | "random"

const LINK_EXTRACT_INPUT_TYPE = 13
const MAX_ORDER_COUNT = 100

const LINK_PATTERN = /https?:\/\/[^\s"'<>，。；;、]+/gi

function randomMultipleInRange(min: number, max: number, step: number) {
  const first = Math.ceil(min / step) * step
  const last = Math.floor(max / step) * step
  if (first > last) return first
  const count = Math.floor((last - first) / step) + 1
  return first + Math.floor(Math.random() * count) * step
}

function extractLinks(value: string): string[] {
  return value.match(LINK_PATTERN) ?? []
}

function formatAmount(value: string | number): string {
  return Number(value).toFixed(7)
}

function splitLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line !== "")
}

interface AdminOrderDialogProps {
  product: ProductPublic
}

interface ParamRows {
  rows: Array<Record<string, string>>
}

export const AdminOrderDialog = ({ product }: AdminOrderDialogProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const inventory = product.inventory
  const minQuantity = inventory?.min_quantity ?? 1
  const maxQuantity = inventory?.max_quantity ?? 1_000_000
  const purchaseStep = Math.max(1, Number(inventory?.purchase_step) || 1)
  const isBatch = inventory?.is_batch ?? true
  const buyParams = product.buy_params ?? []
  const paramLabels = new Map(
    buyParams.map((param) => [param.key, param.label]),
  )

  const [isOpen, setIsOpen] = useState(false)
  const [mode, setMode] = useState<OrderMode>("normal")
  const [quantity, setQuantity] = useState(minQuantity)
  const [randomMin, setRandomMin] = useState(minQuantity)
  const [randomMax, setRandomMax] = useState(maxQuantity)
  const [remark, setRemark] = useState("")
  const [paramValues, setParamValues] = useState<Record<string, string>>({})
  const [errorMessage, setErrorMessage] = useState("")
  const [result, setResult] = useState<AdminOrdersPublic | null>(null)
  const [submittedOrders, setSubmittedOrders] = useState<OrderCreate[]>([])
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [pendingOrders, setPendingOrders] = useState<OrderCreate[]>([])

  const visibleParams = buyParams.filter(
    (param) => !param.is_hidden && !param.use_default,
  )
  const editableParams = visibleParams.filter((param) => param.is_edit)
  const linkParams = editableParams.filter(
    (param) => param.input_type === LINK_EXTRACT_INPUT_TYPE,
  )

  const openDialog = () => {
    setMode("normal")
    setQuantity(minQuantity)
    setRandomMin(minQuantity)
    setRandomMax(maxQuantity)
    setRemark("")
    setParamValues({})
    setErrorMessage("")
    setResult(null)
    setSubmittedOrders([])
    setConfirmOpen(false)
    setPendingOrders([])
    setIsOpen(true)
  }

  const unitPrice = Number(product.pricing?.cost_price ?? 0)
  const pendingTotalAmount = pendingOrders.reduce(
    (total, order) => total + unitPrice * Number(order.items[0]?.quantity ?? 0),
    0,
  )

  const resolveParamValue = (param: ProductBuyParamPublic) => {
    const edited = paramValues[param.key]
    if (edited !== undefined) return edited
    return param.default_value ?? param.value ?? ""
  }

  const validateQuantity = (value: number): string | null => {
    if (!Number.isInteger(value) || value < 1) {
      return "购买数量必须是正整数"
    }
    if (value < minQuantity) {
      return `购买数量不能小于最小购买数量 ${minQuantity}`
    }
    if (value > maxQuantity) {
      return `购买数量不能大于最大购买数量 ${maxQuantity}`
    }
    if (!isBatch && value > 1) {
      return "该商品不支持批量购买"
    }
    if (value % purchaseStep !== 0) {
      return `购买数量必须是 ${purchaseStep} 的整数倍`
    }
    return null
  }

  const buildParamRows = (): ParamRows | string => {
    const linkValues = new Map<string, string[]>()
    const lineValues = new Map<string, string[]>()

    for (const param of linkParams) {
      const links = extractLinks(resolveParamValue(param))
      if (links.length === 0) {
        return `${param.label} 未提取到链接`
      }
      linkValues.set(param.key, links)
    }

    const lineCounts: number[] = []
    for (const param of editableParams) {
      if (param.input_type === LINK_EXTRACT_INPUT_TYPE) continue
      const lines = splitLines(resolveParamValue(param))
      if (param.is_required && lines.length === 0) {
        return `缺少必填下单参数: ${param.label}`
      }
      lineValues.set(param.key, lines)
      lineCounts.push(lines.length)
    }

    const linkCounts = new Set(
      [...linkValues.values()].map((links) => links.length),
    )
    if (linkCounts.size > 1) {
      return "各链接参数提取到的链接数量不一致"
    }

    const linkOrderCount =
      linkParams.length > 0
        ? (linkValues.get(linkParams[0].key)?.length ?? 0)
        : 0
    const multiLineCounts = new Set(lineCounts.filter((count) => count > 1))
    if (multiLineCounts.size > 1) {
      return "下单参数行数不一致"
    }
    const lineOrderCount =
      multiLineCounts.size === 1 ? [...multiLineCounts][0] : 1
    const orderCount = linkOrderCount > 0 ? linkOrderCount : lineOrderCount
    if (orderCount < 1 || orderCount > MAX_ORDER_COUNT) {
      return `订单数量必须是 1-${MAX_ORDER_COUNT} 的整数`
    }

    for (const param of editableParams) {
      if (param.input_type === LINK_EXTRACT_INPUT_TYPE) continue
      const lines = lineValues.get(param.key) ?? []
      if (lines.length > 1 && lines.length !== orderCount) {
        return "下单参数行数不一致"
      }
    }

    const rows: Array<Record<string, string>> = []
    for (let index = 0; index < orderCount; index++) {
      const params: Record<string, string> = {}
      for (const param of visibleParams) {
        const values = linkValues.get(param.key) ?? lineValues.get(param.key)
        let value = resolveParamValue(param)
        if (values && values.length > 0) {
          value = values.length === 1 ? values[0] : (values[index] ?? "")
        }
        if (value !== "") {
          params[param.key] = value
        }
      }
      rows.push(params)
    }
    return { rows }
  }

  const validateForm = (): string | null => {
    if (mode === "normal") {
      const quantityError = validateQuantity(quantity)
      if (quantityError) return quantityError
      const built = buildParamRows()
      return typeof built === "string" ? built : null
    }

    if (mode === "batch") {
      const quantityError = validateQuantity(quantity)
      if (quantityError) return quantityError
      const built = buildParamRows()
      return typeof built === "string" ? built : null
    }

    const minError = validateQuantity(randomMin)
    if (minError) return `随机范围最小值：${minError}`
    const maxError = validateQuantity(randomMax)
    if (maxError) return `随机范围最大值：${maxError}`
    if (randomMin > randomMax) return "随机数量最小值不能大于最大值"
    if (
      Math.ceil(randomMin / purchaseStep) * purchaseStep >
      Math.floor(randomMax / purchaseStep) * purchaseStep
    ) {
      return `该范围内没有 ${purchaseStep} 的整数倍数量`
    }
    const built = buildParamRows()
    return typeof built === "string" ? built : null
  }

  const buildOrders = (): OrderCreate[] => {
    const makeOrder = (
      itemQuantity: number,
      orderParams: Record<string, string>,
    ): OrderCreate => ({
      items: [
        {
          product_id: product.id,
          quantity: itemQuantity,
          params: orderParams,
        },
      ],
      remark: remark.trim() || null,
    })

    if (mode === "normal") {
      const built = buildParamRows()
      if (typeof built === "string") return []
      return built.rows.map((rowParams) => makeOrder(quantity, rowParams))
    }

    const built = buildParamRows()
    if (typeof built === "string") return []
    const quantities = Array.from({ length: built.rows.length }, () =>
      mode === "batch"
        ? quantity
        : randomMultipleInRange(randomMin, randomMax, purchaseStep),
    )
    return built.rows.map((rowParams, index) =>
      makeOrder(quantities[index], rowParams),
    )
  }

  const mutation = useMutation({
    mutationFn: (orders: OrderCreate[]) =>
      OrdersService.createAdminOrdersApi({
        requestBody: { orders },
      }),
    onSuccess: (data) => {
      setResult(data)
      showSuccessToast(
        `下单完成：成功 ${data.success_count} 单，失败 ${data.failure_count} 单`,
      )
      queryClient.invalidateQueries({ queryKey: ["orders"] })
      queryClient.invalidateQueries({ queryKey: ["products"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const onSubmit = () => {
    const validationMessage = validateForm()
    if (validationMessage) {
      setErrorMessage(validationMessage)
      return
    }
    setErrorMessage("")
    const orders = buildOrders()
    setPendingOrders(orders)
    setConfirmOpen(true)
  }

  const confirmSubmit = () => {
    setResult(null)
    setSubmittedOrders(pendingOrders)
    mutation.mutate(pendingOrders)
    setConfirmOpen(false)
  }

  return (
    <>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={openDialog}
      >
        <ShoppingCart />
        管理员下单
      </DropdownMenuItem>
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>管理员下单</DialogTitle>
            <DialogDescription>
              {product.name}：订单记录在当前管理员名下
            </DialogDescription>
            <DialogDescription>
              单价：{product.pricing?.cost_price}
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[70vh] space-y-5 overflow-y-auto pr-1 [scrollbar-width:thin] [scrollbar-color:var(--border)_transparent] [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar]:h-2 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border">
            <Tabs
              value={mode}
              onValueChange={(value) => {
                setMode(value as OrderMode)
                setErrorMessage("")
                setResult(null)
              }}
            >
              <TabsList>
                <TabsTrigger value="normal">普通下单</TabsTrigger>
                {isBatch && (
                  <>
                    <TabsTrigger value="batch">批量下单</TabsTrigger>
                    <TabsTrigger value="random">随机数量</TabsTrigger>
                  </>
                )}
              </TabsList>
              <TabsContent value="normal">
                <div className="grid gap-1.5">
                  <Label htmlFor="admin-order-quantity">
                    购买数量（可购 {minQuantity}-{maxQuantity}）
                  </Label>
                  <Input
                    id="admin-order-quantity"
                    type="number"
                    min={minQuantity}
                    max={maxQuantity}
                    step={purchaseStep}
                    value={quantity}
                    onChange={(event) =>
                      setQuantity(Number(event.target.value))
                    }
                  />
                </div>
              </TabsContent>
              <TabsContent value="batch">
                <div className="grid gap-1.5">
                  <Label htmlFor="admin-batch-quantity">
                    每单数量（可购 {minQuantity}-{maxQuantity}）
                  </Label>
                  <Input
                    id="admin-batch-quantity"
                    type="number"
                    min={minQuantity}
                    max={maxQuantity}
                    step={purchaseStep}
                    value={quantity}
                    onChange={(event) =>
                      setQuantity(Number(event.target.value))
                    }
                  />
                </div>
              </TabsContent>
              <TabsContent value="random">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="grid gap-1.5">
                    <Label htmlFor="admin-random-min">最小数量</Label>
                    <Input
                      id="admin-random-min"
                      type="number"
                      min={1}
                      step={purchaseStep}
                      value={randomMin}
                      onChange={(event) =>
                        setRandomMin(Number(event.target.value))
                      }
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="admin-random-max">最大数量</Label>
                    <Input
                      id="admin-random-max"
                      type="number"
                      min={1}
                      step={purchaseStep}
                      value={randomMax}
                      onChange={(event) =>
                        setRandomMax(Number(event.target.value))
                      }
                    />
                  </div>
                </div>
              </TabsContent>
            </Tabs>

            {visibleParams.length > 0 && (
              <section className="space-y-3">
                <h3 className="text-sm font-semibold">下单参数</h3>
                <div className="grid gap-4 ">
                  {visibleParams.map((param) => {
                    const isMultiLine =
                      param.input_type === LINK_EXTRACT_INPUT_TYPE ||
                      (mode !== "normal" && param.is_edit)
                    const sharedProps = {
                      id: `admin-param-${param.key}`,
                      value: resolveParamValue(param),
                      placeholder: param.description || undefined,
                      disabled: !param.is_edit,
                    }
                    return (
                      <div key={param.key} className="grid gap-1.5">
                        <Label htmlFor={`admin-param-${param.key}`}>
                          {param.label}
                          {param.is_required && (
                            <span className="text-destructive"> *</span>
                          )}
                        </Label>
                        {isMultiLine ? (
                          <Textarea
                            {...sharedProps}
                            rows={4}
                            onChange={(event) =>
                              setParamValues((current) => ({
                                ...current,
                                [param.key]: event.target.value,
                              }))
                            }
                          />
                        ) : (
                          <Input
                            {...sharedProps}
                            onChange={(event) =>
                              setParamValues((current) => ({
                                ...current,
                                [param.key]: event.target.value,
                              }))
                            }
                          />
                        )}
                      </div>
                    )
                  })}
                </div>
              </section>
            )}

            <div className="grid gap-1.5">
              <Label htmlFor="admin-order-remark">备注</Label>
              <Input
                id="admin-order-remark"
                maxLength={255}
                placeholder="选填"
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
                  <Badge variant="default">成功 {result.success_count}</Badge>
                  <Badge
                    variant={
                      result.failure_count > 0 ? "destructive" : "secondary"
                    }
                  >
                    失败 {result.failure_count}
                  </Badge>
                </div>
                <div className="max-h-56 space-y-2 overflow-y-auto [scrollbar-width:thin] [scrollbar-color:var(--border)_transparent] [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar]:h-2 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border">
                  {result.results.map((item) => {
                    const submittedOrder = submittedOrders[item.index - 1]
                    const params = submittedOrder?.items[0]?.params ?? {}
                    return (
                      <div
                        key={item.index}
                        className="flex items-start justify-between gap-3 rounded-md bg-muted/50 px-3 py-2 text-sm"
                      >
                        <div className="min-w-0 space-y-0.5">
                          {Object.keys(params).length > 0 ? (
                            Object.entries(params).map(([key, value]) => (
                              <div key={key} className="break-all text-xs">
                                <span className="text-muted-foreground">
                                  {paramLabels.get(key) ?? key}:
                                </span>{" "}
                                <span className="font-mono">
                                  {String(value)}
                                </span>
                              </div>
                            ))
                          ) : (
                            <span className="text-muted-foreground">
                              无下单参数
                            </span>
                          )}
                        </div>
                        {item.success && item.order ? (
                          <span className="flex shrink-0 items-center gap-1.5 text-emerald-600">
                            <CheckCircle2 className="size-4 shrink-0" />
                            {formatAmount(item.order.total_amount)}
                          </span>
                        ) : (
                          <span className="flex shrink-0 items-start gap-1.5 text-destructive">
                            <XCircle className="mt-0.5 size-4 shrink-0" />
                            {item.detail || "订单创建失败"}
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
                  <Button variant="outline" disabled={mutation.isPending}>
                    取消
                  </Button>
                </DialogClose>
                <LoadingButton onClick={onSubmit} loading={mutation.isPending}>
                  <ListChecks />
                  提交下单
                </LoadingButton>
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>确认结算金额</DialogTitle>
            <DialogDescription>
              {product.name}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">链接数</span>
              <span>{pendingOrders.length}</span>
            </div>

            <div className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">总数</span>
              <span className="max-w-[65%] break-all text-right">
                {pendingOrders.reduce((sum, order) => sum + (order.items[0]?.quantity ?? 0), 0)}
              </span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-muted-foreground">单价</span>
              <span>{formatAmount(unitPrice)}</span>
            </div>
            <div className="flex items-center justify-between gap-4 border-t pt-3 font-medium">
              <span>结算金额</span>
              <span>{formatAmount(pendingTotalAmount)}</span>
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>
                取消
              </Button>
            </DialogClose>
            <LoadingButton onClick={confirmSubmit} loading={mutation.isPending}>
              确认提交
            </LoadingButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default AdminOrderDialog
