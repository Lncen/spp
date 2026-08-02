import { useQuery, useSuspenseQuery } from "@tanstack/react-query"
import { Suspense, useState } from "react"

import { ProductCategoriesService, ProductsService } from "@/client"
import type { ProductType } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import {
  flattenProductCategories,
  getProductCategoryPath,
} from "@/components/Admin/ProductCategories/types"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import AddProduct from "./AddProduct"
import { columns } from "./columns"
import { PRODUCT_TYPE_OPTIONS } from "./constants"
import PendingProducts from "./PendingProducts"

const NONE = "none"

function toProductType(value: string): ProductType | undefined {
  if (value === NONE) return undefined
  return PRODUCT_TYPE_OPTIONS.find((option) => String(option.value) === value)
    ?.value
}

interface ProductsFilters {
  productType: string
  categoryId: string
}

function getProductsQueryOptions(filters: ProductsFilters) {
  return {
    queryFn: () =>
      ProductsService.readProducts({
        skip: 0,
        limit: 100,
        productType: toProductType(filters.productType),
        categoryId: filters.categoryId === NONE ? undefined : filters.categoryId,
      }),
    queryKey: ["products", filters.productType, filters.categoryId],
  }
}

function ProductsTableContent({ filters }: { filters: ProductsFilters }) {
  const { data: products } = useSuspenseQuery(getProductsQueryOptions(filters))

  return <DataTable columns={columns} data={products.data} />
}

function ProductsTable({ filters }: { filters: ProductsFilters }) {
  return (
    <Suspense fallback={<PendingProducts />}>
      <ProductsTableContent filters={filters} />
    </Suspense>
  )
}

export const Products = () => {
  const [filters, setFilters] = useState<ProductsFilters>({
    productType: NONE,
    categoryId: NONE,
  })
  const { data: categories } = useQuery({
    queryKey: ["product-categories"],
    queryFn: () => ProductCategoriesService.readProductCategories(),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight">商品管理</h2>
          <p className="text-muted-foreground">
            管理商品信息、定价、库存与履约配置
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={filters.categoryId}
            onValueChange={(categoryId) =>
              setFilters((current) => ({ ...current, categoryId }))
            }
          >
            <SelectTrigger className="w-52">
              <SelectValue placeholder="商品分类" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>全部分类</SelectItem>
              {flattenProductCategories(categories?.data ?? []).map(
                (category) => (
                  <SelectItem key={category.id} value={category.id}>
                    {getProductCategoryPath(
                      categories?.data ?? [],
                      category.id,
                    ) ?? category.name}
                  </SelectItem>
                ),
              )}
            </SelectContent>
          </Select>
          <Select
            value={filters.productType}
            onValueChange={(productType) =>
              setFilters((current) => ({ ...current, productType }))
            }
          >
            <SelectTrigger className="w-40">
              <SelectValue placeholder="商品类型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>全部类型</SelectItem>
              {PRODUCT_TYPE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={String(option.value)}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <AddProduct />
        </div>
      </div>
      <ProductsTable filters={filters} />
    </div>
  )
}
