import { z } from "zod"

import type {
  ProductCategoryCreate,
  ProductCategoryPublic,
  ProductCategoryTreePublic,
  ProductCategoryUpdate,
} from "@/client"

export const productCategoryFormSchema = z.object({
  name: z
    .string()
    .min(1, "分类名称不能为空")
    .max(100, "分类名称不能超过 100 个字符"),
  parentId: z.string().nullable(),
  iconId: z.string().nullable(),
  sort: z.coerce.number().int().min(0, "排序不能小于 0"),
  isActive: z.boolean(),
})

export type ProductCategoryFormValues = z.infer<
  typeof productCategoryFormSchema
>

export type ProductCategoryRow = ProductCategoryTreePublic & {
  subRows: ProductCategoryRow[]
}

export function toProductCategoryRows(
  categories: ProductCategoryTreePublic[],
): ProductCategoryRow[] {
  return categories.map((category) => ({
    ...category,
    subRows: toProductCategoryRows(category.children ?? []),
  }))
}

export function flattenProductCategories(
  categories: ProductCategoryTreePublic[],
): ProductCategoryTreePublic[] {
  return categories.flatMap((category) => [
    category,
    ...flattenProductCategories(category.children ?? []),
  ])
}

export function getProductCategoryPath(
  categories: ProductCategoryTreePublic[],
  categoryId: string | null,
): string | null {
  if (!categoryId) return null
  for (const category of categories) {
    if (category.id === categoryId) return category.name
    const childPath = getProductCategoryPath(
      category.children ?? [],
      categoryId,
    )
    if (childPath) {
      return `${category.name} / ${childPath}`
    }
  }
  return null
}

export function toProductCategoryFormValues(
  category?: ProductCategoryPublic,
): ProductCategoryFormValues {
  return {
    name: category?.name ?? "",
    parentId: category?.parent_id ?? null,
    iconId: category?.icon_id ?? null,
    sort: category?.sort ?? 0,
    isActive: category?.is_active ?? true,
  }
}

export function toProductCategoryCreate(
  values: ProductCategoryFormValues,
): ProductCategoryCreate {
  return {
    name: values.name,
    parent_id: values.parentId || null,
    icon_id: values.iconId || null,
    sort: values.sort,
    is_active: values.isActive,
  }
}

export function toProductCategoryUpdate(
  values: ProductCategoryFormValues,
): ProductCategoryUpdate {
  return {
    name: values.name,
    parent_id: values.parentId || null,
    icon_id: values.iconId || null,
    sort: values.sort,
    is_active: values.isActive,
  }
}
