import { z } from "zod"

import type {
  ProductBuyParamCreate,
  ProductCreate,
  ProductFulfillmentCreate,
  ProductInventoryCreate,
  ProductPricingCreate,
  ProductPublic,
  ProductUpdate,
} from "@/client"

export type PriceRule = "template" | "fixed" | "coefficient"

export type BuyParamFormValues = {
  key: string
  label: string
  value: string
  description: string
  inputType: number
  typeConfig: Record<string, unknown>[]
  defaultValue: string
  useDefault: boolean
  isRequired: boolean
  isHidden: boolean
  isEdit: boolean
  validateMin: number
  validateMax: number
}

export type ProductFormValues = {
  name: string
  categoryId: string
  sourceType: number
  status: number
  type: number
  isClosed: boolean
  sort: number
  supplierId: string
  skuId: string
  priceRule: PriceRule
  priceTemplateId: string
  costPrice: string
  lossPrice: string
  fixedPrice: string
  itemCoefficient: string
  priceDisplayPrecision: number
  minQuantity: number
  maxQuantity: number
  isRepeatable: boolean
  isBatch: boolean
  purchaseStep: string
  stock: number
  fulfillmentType: number
  canRefund: boolean
  afterSaleRules: string
  fulfillmentDescription: string
  unit: string
  inputFieldsOverridden: boolean
  paramsTemplate: Record<string, unknown>[]
  buyParams: BuyParamFormValues[]
}

export const emptyBuyParam = (): BuyParamFormValues => ({
  key: "",
  label: "",
  value: "",
  description: "",
  inputType: 1,
  typeConfig: [],
  defaultValue: "",
  useDefault: false,
  isRequired: true,
  isHidden: false,
  isEdit: false,
  validateMin: 1,
  validateMax: 100,
})

export const emptyProductFormValues = (): ProductFormValues => ({
  name: "",
  categoryId: "",
  sourceType: 2,
  status: 1,
  type: 1,
  isClosed: false,
  sort: 0,
  supplierId: "",
  skuId: "",
  priceRule: "template",
  priceTemplateId: "",
  costPrice: "0.00",
  lossPrice: "0.00",
  fixedPrice: "",
  itemCoefficient: "",
  priceDisplayPrecision: 2,
  minQuantity: 1,
  maxQuantity: 1_000_000,
  isRepeatable: false,
  isBatch: true,
  purchaseStep: "1",
  stock: -1,
  fulfillmentType: 1,
  canRefund: false,
  afterSaleRules: "",
  fulfillmentDescription: "",
  unit: "1",
  inputFieldsOverridden: false,
  paramsTemplate: [],
  buyParams: [],
})

const buyParamSchema = z.object({
  key: z
    .string()
    .min(1, "参数 Key 不能为空")
    .max(128, "参数 Key 不能超过 128 个字符"),
  label: z
    .string()
    .min(1, "参数名称不能为空")
    .max(128, "参数名称不能超过 128 个字符"),
  value: z.string().max(128, "参数值不能超过 128 个字符").optional(),
  description: z.string().optional(),
  inputType: z.coerce.number().int().min(1).max(15),
  typeConfig: z.array(z.record(z.string(), z.unknown())).optional(),
  defaultValue: z.string().optional(),
  useDefault: z.boolean(),
  isRequired: z.boolean(),
  isHidden: z.boolean(),
  isEdit: z.boolean(),
  validateMin: z.coerce.number().int().min(0),
  validateMax: z.coerce.number().int().min(0),
})

function parseDecimal(value?: string): number | undefined {
  if (value === undefined || value === null || value.trim() === "") {
    return undefined
  }
  const parsed = Number(value)
  return Number.isNaN(parsed) ? undefined : parsed
}

export const productFormSchema = z
  .object({
    name: z
      .string()
      .min(1, "请输入商品名称")
      .max(255, "商品名称不能超过 255 个字符"),
    categoryId: z.string().optional(),
    sourceType: z.coerce.number().int().min(1).max(8),
    status: z.coerce.number().int().min(1).max(8),
    type: z.coerce.number().int().min(1).max(8),
    isClosed: z.boolean(),
    sort: z.coerce.number().int().min(0),
    supplierId: z.string().optional(),
    skuId: z.string().max(255, "SKU 不能超过 255 个字符").optional(),
    priceRule: z.enum(["template", "fixed", "coefficient"]),
    priceTemplateId: z.string().optional(),
    costPrice: z.string().optional(),
    lossPrice: z.string().optional(),
    fixedPrice: z.string().optional(),
    itemCoefficient: z.string().optional(),
    priceDisplayPrecision: z.coerce.number().int().min(0).max(32767),
    minQuantity: z.coerce.number().int().min(1, "最小购买数量不能小于 1"),
    maxQuantity: z.coerce.number().int().min(1, "最大购买数量不能小于 1"),
    isRepeatable: z.boolean(),
    isBatch: z.boolean(),
    purchaseStep: z.string().optional(),
    stock: z.coerce.number().int().min(-1),
    fulfillmentType: z.coerce.number().int().min(1).max(3),
    canRefund: z.boolean(),
    afterSaleRules: z.string().optional(),
    fulfillmentDescription: z.string().optional(),
    unit: z.string().max(32, "数量单位不能超过 32 个字符").optional(),
    inputFieldsOverridden: z.boolean(),
    paramsTemplate: z.array(z.record(z.string(), z.unknown())).optional(),
    buyParams: z.array(buyParamSchema),
  })
  .superRefine((values, ctx) => {
    if (values.priceRule === "template" && !values.priceTemplateId) {
      ctx.addIssue({
        code: "custom",
        path: ["priceTemplateId"],
        message: "请选择价格模板",
      })
    }
    if (values.priceRule === "fixed") {
      const fixedPrice = parseDecimal(values.fixedPrice)
      if (fixedPrice === undefined || fixedPrice < 0) {
        ctx.addIssue({
          code: "custom",
          path: ["fixedPrice"],
          message: "请输入不小于 0 的固定价格",
        })
      }
    }
    if (values.priceRule === "coefficient") {
      const coefficient = parseDecimal(values.itemCoefficient)
      if (
        coefficient === undefined ||
        coefficient < 0.01 ||
        coefficient > 9.99
      ) {
        ctx.addIssue({
          code: "custom",
          path: ["itemCoefficient"],
          message: "请输入 0.01 到 9.99 之间的系数",
        })
      }
    }
    const costPrice = parseDecimal(values.costPrice)
    if (costPrice !== undefined && costPrice < 0) {
      ctx.addIssue({
        code: "custom",
        path: ["costPrice"],
        message: "成本价不能小于 0",
      })
    }
    const lossPrice = parseDecimal(values.lossPrice)
    if (lossPrice !== undefined && lossPrice < 0) {
      ctx.addIssue({
        code: "custom",
        path: ["lossPrice"],
        message: "固定损耗不能小于 0",
      })
    }
    const purchaseStep = parseDecimal(values.purchaseStep)
    if (purchaseStep !== undefined && purchaseStep <= 0) {
      ctx.addIssue({
        code: "custom",
        path: ["purchaseStep"],
        message: "购买步长必须大于 0",
      })
    }
    if (values.minQuantity > values.maxQuantity) {
      ctx.addIssue({
        code: "custom",
        path: ["maxQuantity"],
        message: "最大购买数量不能小于最小购买数量",
      })
    }
  })

function buildPricing(values: ProductFormValues): ProductPricingCreate {
  return {
    price_template_id:
      values.priceRule === "template" ? values.priceTemplateId : null,
    cost_price: values.costPrice || "0.00",
    loss_price: values.lossPrice || "0.00",
    fixed_price: values.priceRule === "fixed" ? values.fixedPrice || "0" : null,
    item_coefficient:
      values.priceRule === "coefficient" ? values.itemCoefficient : null,
    price_display_precision: values.priceDisplayPrecision,
  }
}

function buildInventory(values: ProductFormValues): ProductInventoryCreate {
  return {
    min_quantity: values.minQuantity,
    max_quantity: values.maxQuantity,
    is_repeatable: values.isRepeatable,
    is_batch: values.isBatch,
    purchase_step: values.purchaseStep || "1",
    stock: values.stock,
  }
}

function buildFulfillment(values: ProductFormValues): ProductFulfillmentCreate {
  return {
    fulfillment_type:
      values.fulfillmentType as ProductFulfillmentCreate["fulfillment_type"],
    can_refund: values.canRefund,
    after_sale_rules: values.afterSaleRules || "",
    description: values.fulfillmentDescription || "",
    unit: values.unit || "1",
    input_fields_overridden: values.inputFieldsOverridden,
    params_template: values.paramsTemplate,
  }
}

function buildBuyParam(param: BuyParamFormValues): ProductBuyParamCreate {
  return {
    key: param.key,
    label: param.label,
    value: param.value || "",
    description: param.description || "",
    input_type: param.inputType as ProductBuyParamCreate["input_type"],
    type_config: param.typeConfig,
    default_value: param.defaultValue || "",
    use_default: param.useDefault,
    is_required: param.isRequired,
    is_hidden: param.isHidden,
    is_edit: param.isEdit,
    validate_min: param.validateMin,
    validate_max: param.validateMax,
  }
}

export function productFormToCreate(values: ProductFormValues): ProductCreate {
  return {
    name: values.name.trim(),
    category_id: values.categoryId || null,
    source_type: values.sourceType as ProductCreate["source_type"],
    status: values.status as ProductCreate["status"],
    is_closed: values.isClosed,
    sort: values.sort,
    type: values.type as ProductCreate["type"],
    supplier: values.supplierId
      ? { supplier_id: values.supplierId, sku_id: values.skuId || null }
      : null,
    pricing: buildPricing(values),
    inventory: buildInventory(values),
    fulfillment: buildFulfillment(values),
    buy_params: values.buyParams.map(buildBuyParam),
  }
}

export function productFormToUpdate(values: ProductFormValues): ProductUpdate {
  return {
    name: values.name.trim(),
    category_id: values.categoryId || null,
    source_type: values.sourceType as ProductUpdate["source_type"],
    status: values.status as ProductUpdate["status"],
    is_closed: values.isClosed,
    sort: values.sort,
    type: values.type as ProductUpdate["type"],
    supplier: values.supplierId
      ? { supplier_id: values.supplierId, sku_id: values.skuId || null }
      : null,
    pricing: buildPricing(values),
    inventory: buildInventory(values),
    fulfillment: buildFulfillment(values),
    buy_params: values.buyParams.map(buildBuyParam),
  }
}

export function productToFormValues(product: ProductPublic): ProductFormValues {
  const pricing = product.pricing
  const inventory = product.inventory
  const fulfillment = product.fulfillment
  const priceRule: PriceRule =
    pricing?.fixed_price != null
      ? "fixed"
      : pricing?.item_coefficient != null
        ? "coefficient"
        : "template"

  return {
    name: product.name,
    categoryId: product.category_id ?? "",
    sourceType: product.source_type,
    status: product.status,
    type: product.type,
    isClosed: product.is_closed,
    sort: product.sort,
    supplierId: product.supplier?.supplier_id ?? "",
    skuId: product.supplier?.sku_id ?? "",
    priceRule,
    priceTemplateId: pricing?.price_template_id ?? "",
    costPrice: pricing?.cost_price ?? "",
    lossPrice: pricing?.loss_price ?? "",
    fixedPrice: pricing?.fixed_price ?? "",
    itemCoefficient: pricing?.item_coefficient ?? "",
    priceDisplayPrecision: pricing?.price_display_precision ?? 2,
    minQuantity: inventory?.min_quantity ?? 1,
    maxQuantity: inventory?.max_quantity ?? 1_000_000,
    isRepeatable: inventory?.is_repeatable ?? false,
    isBatch: inventory?.is_batch ?? true,
    purchaseStep: inventory?.purchase_step ?? "1",
    stock: inventory?.stock ?? -1,
    fulfillmentType: fulfillment?.fulfillment_type ?? 1,
    canRefund: fulfillment?.can_refund ?? false,
    afterSaleRules: fulfillment?.after_sale_rules ?? "",
    fulfillmentDescription: fulfillment?.description ?? "",
    unit: fulfillment?.unit ?? "1",
    inputFieldsOverridden: fulfillment?.input_fields_overridden ?? false,
    paramsTemplate: fulfillment?.params_template ?? [],
    buyParams: (product.buy_params ?? []).map((param) => ({
      key: param.key,
      label: param.label,
      value: param.value,
      description: param.description,
      inputType: param.input_type,
      typeConfig: param.type_config,
      defaultValue: param.default_value,
      useDefault: param.use_default,
      isRequired: param.is_required,
      isHidden: param.is_hidden,
      isEdit: param.is_edit,
      validateMin: param.validate_min,
      validateMax: param.validate_max,
    })),
  }
}
