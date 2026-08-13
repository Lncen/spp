import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  CalendarDays,
  Clock,
  Image as ImageIcon,
  Plus,
  Trash2,
} from "lucide-react"
import { useEffect } from "react"
import { useFieldArray, useForm } from "react-hook-form"

import type { ProductPublic } from "@/client"
import {
  ImagesService,
  PriceTemplatesService,
  ProductCategoriesService,
  ProductsService,
  SuppliersService,
} from "@/client"
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
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import {
  flattenProductCategories,
  getProductCategoryPath,
} from "../ProductCategories/types"
import {
  INPUT_TYPE_OPTIONS,
  PRODUCT_STATUS_OPTIONS,
  PRODUCT_TYPE_OPTIONS,
  REDEEM_TYPE_OPTIONS,
  SOURCE_TYPE_OPTIONS,
  syncStatusLabel,
} from "./constants"
import {
  emptyBuyParam,
  emptyProductFormValues,
  type ProductFormValues,
  productFormSchema,
  productFormToCreate,
  productFormToUpdate,
  productToFormValues,
} from "./types"

interface ProductFormDialogProps {
  product?: ProductPublic
  isOpen: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

const PRICE_RULE_OPTIONS = [
  { value: "template", label: "价格模板" },
  { value: "fixed", label: "固定价格" },
  { value: "coefficient", label: "商品系数" },
] as const

function stringOrEmpty(value: string) {
  return value || "none"
}

function emptyOnNone(value: string) {
  return value === "none" ? "" : value
}

function formatDateTime(value: string | null | undefined) {
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

function SectionHeading({ step, title }: { step: string; title: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-primary/10 text-xs font-semibold text-primary">
        {step}
      </span>
      <h3 className="text-sm font-semibold">{title}</h3>
    </div>
  )
}

function UpstreamInfoItem({
  label,
  value,
}: {
  label: string
  value?: string | null
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b py-2 text-sm">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value || "—"}</span>
    </div>
  )
}

const ProductFormDialog = ({
  product,
  isOpen,
  onOpenChange,
  onSuccess,
}: ProductFormDialogProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: categories } = useQuery({
    queryKey: ["product-categories"],
    queryFn: () => ProductCategoriesService.readProductCategories(),
    enabled: isOpen,
  })
  const { data: priceTemplates } = useQuery({
    queryKey: ["price-templates"],
    queryFn: () =>
      PriceTemplatesService.readPriceTemplates({ skip: 0, limit: 100 }),
    enabled: isOpen,
  })
  const { data: suppliers } = useQuery({
    queryKey: ["suppliers"],
    queryFn: () => SuppliersService.readSuppliers({ skip: 0, limit: 100 }),
    enabled: isOpen,
  })
  const { data: images } = useQuery({
    queryKey: ["images"],
    queryFn: () => ImagesService.readImages({ skip: 0, limit: 200 }),
    enabled: isOpen,
  })

  const form = useForm<ProductFormValues>({
    resolver: zodResolver(productFormSchema) as any,
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: emptyProductFormValues(),
  })

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "buyParams",
  })

  useEffect(() => {
    if (isOpen) {
      form.reset(
        product ? productToFormValues(product) : emptyProductFormValues(),
      )
    }
  }, [isOpen, product, form])

  const mutation = useMutation({
    mutationFn: (values: ProductFormValues) =>
      product
        ? ProductsService.updateProduct({
            productId: product.id,
            requestBody: productFormToUpdate(values),
          })
        : ProductsService.createProduct({
            requestBody: productFormToCreate(values),
          }),
    onSuccess: (data) => {
      showSuccessToast(
        product ? `商品 "${data.name}" 已更新` : `商品 "${data.name}" 已创建`,
      )
      onOpenChange(false)
      onSuccess?.()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] })
    },
  })

  const onSubmit = (values: ProductFormValues) => {
    mutation.mutate(values)
  }

  const priceRule = form.watch("priceRule")
  const imageId = form.watch("imageId")
  const selectedImage = images?.data.find((image) => image.id === imageId)

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>{product ? "编辑商品" : "添加商品"}</DialogTitle>
          <DialogDescription>
            {product
              ? `修改「${product.name}」的商品信息。`
              : "创建商品并配置定价、库存、履约与下单参数。"}
          </DialogDescription>
          {product && (
            <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 rounded-lg bg-muted/60 px-3.5 py-2.5 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1.5">
                <CalendarDays className="size-3.5" />
                创建时间：{formatDateTime(product.created_at)}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Clock className="size-3.5" />
                更新时间：{formatDateTime(product.updated_at)}
              </span>
            </div>
          )}
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
            <div className="grid gap-3 py-2 max-h-[75vh] overflow-y-auto pr-2 lg:grid-cols-2">
              <div className="space-y-5">
                <section className="space-y-4 rounded-lg border bg-card p-4">
                  <SectionHeading step="01" title="基本信息" />
                  <div className="flex items-end gap-4">
                    <div className="flex size-63 shrink-0 items-center justify-center overflow-hidden rounded-lg border bg-muted/60">
                      {selectedImage ? (
                        <img
                          src={selectedImage.url}
                          alt=""
                          className="size-full object-cover"
                        />
                      ) : (
                        <ImageIcon className="size-20 text-muted-foreground" />
                      )}
                    </div>
                    <FormField
                      control={form.control}
                      name="imageId"
                      render={({ field }) => (
                        <FormItem className="flex-1">
                          <FormLabel>商品图片</FormLabel>
                          <Select
                            value={stringOrEmpty(field.value)}
                            onValueChange={(value) =>
                              field.onChange(emptyOnNone(value))
                            }
                          >
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue placeholder="从图片库选择主图" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              <SelectItem value="none">无主图</SelectItem>
                              {images?.data.map((image) => (
                                <SelectItem key={image.id} value={image.id}>
                                  <span className="flex items-center gap-2">
                                    <img
                                      src={image.url}
                                      alt=""
                                      className="size-5 rounded object-cover"
                                    />
                                    {image.filename}
                                  </span>
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField
                      control={form.control}
                      name="name"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>
                            商品名称 <span className="text-destructive">*</span>
                          </FormLabel>
                          <FormControl>
                            <Input
                              placeholder="例如：会员月卡"
                              type="text"
                              {...field}
                              required
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="categoryId"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>
                            商品分类
                            <span className="text-destructive">*</span>
                          </FormLabel>
                          <Select
                            value={stringOrEmpty(field.value)}
                            onValueChange={(value) =>
                              field.onChange(emptyOnNone(value))
                            }
                          >
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue placeholder="选择分类" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {flattenProductCategories(
                                categories?.data ?? [],
                              ).map((category) => (
                                <SelectItem
                                  key={category.id}
                                  value={category.id}
                                >
                                  {getProductCategoryPath(
                                    categories?.data ?? [],
                                    category.id,
                                  ) ?? category.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField
                      control={form.control}
                      name="type"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>商品类型</FormLabel>
                          <Select
                            value={String(field.value)}
                            onValueChange={(value) =>
                              field.onChange(Number(value))
                            }
                          >
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {PRODUCT_TYPE_OPTIONS.map((option) => (
                                <SelectItem
                                  key={option.value}
                                  value={String(option.value)}
                                >
                                  {option.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="status"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>商品状态</FormLabel>
                          <Select
                            value={String(field.value)}
                            onValueChange={(value) =>
                              field.onChange(Number(value))
                            }
                          >
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {PRODUCT_STATUS_OPTIONS.map((option) => (
                                <SelectItem
                                  key={option.value}
                                  value={String(option.value)}
                                >
                                  {option.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField
                      control={form.control}
                      name="sourceType"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>商品来源</FormLabel>
                          <Select
                            value={String(field.value)}
                            onValueChange={(value) =>
                              field.onChange(Number(value))
                            }
                          >
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {SOURCE_TYPE_OPTIONS.map((option) => (
                                <SelectItem
                                  key={option.value}
                                  value={String(option.value)}
                                >
                                  {option.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="sort"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>排序权重</FormLabel>
                          <FormControl>
                            <Input type="number" min={0} {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <FormField
                    control={form.control}
                    name="isClosed"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center gap-2 space-y-0 pt-2">
                        <FormControl>
                          <Checkbox
                            checked={field.value}
                            onCheckedChange={field.onChange}
                          />
                        </FormControl>
                        <FormLabel>关闭下单</FormLabel>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </section>

                <section className="space-y-4 rounded-lg border bg-card p-4">
                  <SectionHeading
                    step="02"
                    title={product ? "上游商品" : "货源配置"}
                  />
                  {product ? (
                    <div className="grid gap-3 sm:grid-cols-2">
                      <UpstreamInfoItem
                        label="供应商"
                        value={product.supplier?.supplier_name}
                      />
                      <UpstreamInfoItem
                        label="上游 SKU"
                        value={product.supplier?.sku_id}
                      />
                      <UpstreamInfoItem
                        label="上游名称"
                        value={product.supplier?.upstream_name}
                      />
                      <UpstreamInfoItem
                        label="同步状态"
                        value={syncStatusLabel(product.sync_status)}
                      />
                    </div>
                  ) : (
                    <div className="grid gap-4 sm:grid-cols-2">
                      <FormField
                        control={form.control}
                        name="supplierId"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>关联供应商</FormLabel>
                            <Select
                              value={stringOrEmpty(field.value)}
                              onValueChange={(value) =>
                                field.onChange(emptyOnNone(value))
                              }
                            >
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue placeholder="选择供应商" />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                <SelectItem value="none">未关联</SelectItem>
                                {suppliers?.data.map((supplier) => (
                                  <SelectItem
                                    key={supplier.id}
                                    value={supplier.id}
                                  >
                                    {supplier.name}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name="skuId"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>供应商 SKU</FormLabel>
                            <FormControl>
                              <Input
                                placeholder="供应商侧商品 SKU"
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                  )}
                </section>
              </div>

              <div className="space-y-5">
                <section className="space-y-4 rounded-lg border bg-card p-4">
                  <SectionHeading step="03" title="定价" />
                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField
                      control={form.control}
                      name="priceRule"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>定价模式</FormLabel>
                          <Select
                            value={field.value}
                            onValueChange={(value) =>
                              field.onChange(
                                value as ProductFormValues["priceRule"],
                              )
                            }
                          >
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {PRICE_RULE_OPTIONS.map((option) => (
                                <SelectItem
                                  key={option.value}
                                  value={option.value}
                                >
                                  {option.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    {priceRule === "template" && (
                      <FormField
                        control={form.control}
                        name="priceTemplateId"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>价格模板</FormLabel>
                            <Select
                              value={stringOrEmpty(field.value)}
                              onValueChange={(value) =>
                                field.onChange(emptyOnNone(value))
                              }
                            >
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue placeholder="选择价格模板" />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                <SelectItem value="none">未选择</SelectItem>
                                {priceTemplates?.data.map((template) => (
                                  <SelectItem
                                    key={template.id}
                                    value={template.id}
                                  >
                                    {template.name}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    )}
                    {priceRule === "fixed" && (
                      <FormField
                        control={form.control}
                        name="fixedPrice"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>
                              固定售价{" "}
                              <span className="text-destructive">*</span>
                            </FormLabel>
                            <FormControl>
                              <Input
                                type="number"
                                min={0}
                                step="0.00000001"
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    )}
                    {priceRule === "coefficient" && (
                      <FormField
                        control={form.control}
                        name="itemCoefficient"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>
                              商品系数{" "}
                              <span className="text-destructive">*</span>
                            </FormLabel>
                            <FormControl>
                              <Input
                                type="number"
                                min={0.01}
                                max={9.99}
                                step="0.0001"
                                {...field}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    )}
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField
                      control={form.control}
                      name="costPrice"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>成本价</FormLabel>
                          <FormControl>
                            <Input
                              type="number"
                              min={0}
                              step="0.00000001"
                              {...field}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="lossPrice"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>损耗价格</FormLabel>
                          <FormControl>
                            <Input
                              type="number"
                              min={0}
                              step="0.00000001"
                              {...field}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                  <FormField
                    control={form.control}
                    name="priceDisplayPrecision"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>显示精度</FormLabel>
                        <FormControl>
                          <Input type="number" min={0} max={32767} {...field} />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </section>

                <section className="space-y-4 rounded-lg border bg-card p-4">
                  <SectionHeading step="04" title="库存与购买" />
                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField
                      control={form.control}
                      name="minQuantity"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>最小购买量</FormLabel>
                          <FormControl>
                            <Input type="number" min={1} {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="maxQuantity"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>最大购买量</FormLabel>
                          <FormControl>
                            <Input type="number" min={1} {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="purchaseStep"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>购买步长</FormLabel>
                          <FormControl>
                            <Input type="number" min={1} step={1} {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="stock"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>当前库存</FormLabel>
                          <FormControl>
                            <Input
                              type="number"
                              min={-1}
                              placeholder="-1 表示无限"
                              {...field}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="isRepeatable"
                      render={({ field }) => (
                        <FormItem className="flex flex-row items-center gap-2 space-y-0 pt-6">
                          <FormControl>
                            <Checkbox
                              checked={field.value}
                              onCheckedChange={field.onChange}
                            />
                          </FormControl>
                          <FormLabel>可重复购买</FormLabel>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="isBatch"
                      render={({ field }) => (
                        <FormItem className="flex flex-row items-center gap-2 space-y-0 pt-6">
                          <FormControl>
                            <Checkbox
                              checked={field.value}
                              onCheckedChange={field.onChange}
                            />
                          </FormControl>
                          <FormLabel>批量购买</FormLabel>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </section>
                <section className="space-y-4 rounded-lg border bg-card p-4 lg:col-span-2">
                  <SectionHeading step="05" title="履约与售后" />
                  <div className="grid gap-4 sm:grid-cols-3">
                    <FormField
                      control={form.control}
                      name="fulfillmentType"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>履约方式</FormLabel>
                          <Select
                            value={String(field.value)}
                            onValueChange={(value) =>
                              field.onChange(Number(value))
                            }
                          >
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {REDEEM_TYPE_OPTIONS.map((option) => (
                                <SelectItem
                                  key={option.value}
                                  value={String(option.value)}
                                >
                                  {option.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="unit"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>计量单位</FormLabel>
                          <FormControl>
                            <Input maxLength={32} placeholder="1" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="canRefund"
                      render={({ field }) => (
                        <FormItem className="flex flex-row items-center gap-2 space-y-0 pt-6">
                          <FormControl>
                            <Checkbox
                              checked={field.value}
                              onCheckedChange={field.onChange}
                            />
                          </FormControl>
                          <FormLabel>支持退款</FormLabel>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <FormField
                      control={form.control}
                      name="afterSaleRules"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>售后规则</FormLabel>
                          <FormControl>
                            <Input placeholder="售后规则" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="fulfillmentDescription"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>商品描述</FormLabel>
                          <FormControl>
                            <Input placeholder="商品描述" {...field} />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </section>
              </div>

              <section className="space-y-4 rounded-lg border bg-card p-4 lg:col-span-2">
                <div className="flex items-center justify-between">
                  <SectionHeading step="06" title="下单参数" />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => append(emptyBuyParam())}
                  >
                    <Plus />
                    添加参数
                  </Button>
                </div>

                {fields.length === 0 && (
                  <p className="text-sm text-muted-foreground">暂无下单参数</p>
                )}

                {fields.map((field, index) => (
                  <div
                    key={field.id}
                    className="space-y-3 rounded-md border p-4"
                  >
                    <div className="grid gap-3 sm:grid-cols-2">
                      <FormField
                        control={form.control}
                        name={`buyParams.${index}.key`}
                        render={({ field: paramField }) => (
                          <FormItem>
                            <FormLabel>
                              参数 Key{" "}
                              <span className="text-destructive">*</span>
                            </FormLabel>
                            <FormControl>
                              <Input
                                placeholder="例如：account"
                                {...paramField}
                                required
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`buyParams.${index}.label`}
                        render={({ field: paramField }) => (
                          <FormItem>
                            <FormLabel>
                              参数名称{" "}
                              <span className="text-destructive">*</span>
                            </FormLabel>
                            <FormControl>
                              <Input
                                placeholder="例如：账号"
                                {...paramField}
                                required
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`buyParams.${index}.value`}
                        render={({ field: paramField }) => (
                          <FormItem>
                            <FormLabel>参数值</FormLabel>
                            <FormControl>
                              <Input
                                placeholder="固定参数值（可选）"
                                {...paramField}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`buyParams.${index}.description`}
                        render={({ field: paramField }) => (
                          <FormItem>
                            <FormLabel>参数提示</FormLabel>
                            <FormControl>
                              <Input placeholder="填写提示" {...paramField} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`buyParams.${index}.inputType`}
                        render={({ field: paramField }) => (
                          <FormItem>
                            <FormLabel>输入类型</FormLabel>
                            <Select
                              value={String(paramField.value)}
                              onValueChange={(value) =>
                                paramField.onChange(Number(value))
                              }
                            >
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                {INPUT_TYPE_OPTIONS.map((option) => (
                                  <SelectItem
                                    key={option.value}
                                    value={String(option.value)}
                                  >
                                    {option.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`buyParams.${index}.defaultValue`}
                        render={({ field: paramField }) => (
                          <FormItem>
                            <FormLabel>默认值</FormLabel>
                            <FormControl>
                              <Input
                                placeholder="默认值（可选）"
                                {...paramField}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`buyParams.${index}.validateMin`}
                        render={({ field: paramField }) => (
                          <FormItem>
                            <FormLabel>最小长度/值</FormLabel>
                            <FormControl>
                              <Input type="number" min={0} {...paramField} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`buyParams.${index}.validateMax`}
                        render={({ field: paramField }) => (
                          <FormItem>
                            <FormLabel>最大长度/值</FormLabel>
                            <FormControl>
                              <Input type="number" min={0} {...paramField} />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>

                    <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
                      <FormField
                        control={form.control}
                        name={`buyParams.${index}.useDefault`}
                        render={({ field: paramField }) => (
                          <FormItem className="flex flex-row items-center gap-2 space-y-0">
                            <FormControl>
                              <Checkbox
                                checked={paramField.value}
                                onCheckedChange={paramField.onChange}
                              />
                            </FormControl>
                            <FormLabel>使用默认值</FormLabel>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`buyParams.${index}.isRequired`}
                        render={({ field: paramField }) => (
                          <FormItem className="flex flex-row items-center gap-2 space-y-0">
                            <FormControl>
                              <Checkbox
                                checked={paramField.value}
                                onCheckedChange={paramField.onChange}
                              />
                            </FormControl>
                            <FormLabel>必填</FormLabel>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`buyParams.${index}.isHidden`}
                        render={({ field: paramField }) => (
                          <FormItem className="flex flex-row items-center gap-2 space-y-0">
                            <FormControl>
                              <Checkbox
                                checked={paramField.value}
                                onCheckedChange={paramField.onChange}
                              />
                            </FormControl>
                            <FormLabel>隐藏</FormLabel>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <FormField
                        control={form.control}
                        name={`buyParams.${index}.isEdit`}
                        render={({ field: paramField }) => (
                          <FormItem className="flex flex-row items-center gap-2 space-y-0">
                            <FormControl>
                              <Checkbox
                                checked={paramField.value}
                                onCheckedChange={paramField.onChange}
                              />
                            </FormControl>
                            <FormLabel>可修改</FormLabel>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="ml-auto text-destructive"
                          >
                            <Trash2 />
                            移除参数
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>确认移除参数</AlertDialogTitle>
                            <AlertDialogDescription>
                              确定要移除参数“{field.label || field.key}”吗？
                              移除后不可恢复。
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>取消</AlertDialogCancel>
                            <AlertDialogAction onClick={() => remove(index)}>
                              确认移除
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </div>
                ))}
              </section>
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  取消
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                {product ? "保存" : "创建"}
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default ProductFormDialog
