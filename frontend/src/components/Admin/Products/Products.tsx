import { useQuery, useSuspenseQuery } from "@tanstack/react-query"
import type { PaginationState } from "@tanstack/react-table"
import { Search } from "lucide-react"
import { Suspense, useState } from "react"
import type { ProductType } from "@/client"
import { ProductCategoriesService, ProductsService } from "@/client"
import {
  flattenProductCategories,
  getProductCategoryPath,
} from "@/components/Admin/ProductCategories/types"
import { DataTable } from "@/components/Common/DataTable"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import AddProduct from "./AddProduct"
import { columns } from "./columns"
import { PRODUCT_TYPE_OPTIONS } from "./constants"
import PendingProducts from "./PendingProducts"

const NONE = "none"
const SEARCH_DEBOUNCE_MS = 300

function toProductType(value: string): ProductType | undefined {
  if (value === NONE) return undefined
  return PRODUCT_TYPE_OPTIONS.find((option) => String(option.value) === value)
    ?.value
}

interface ProductsFilters {
  productType: string
  categoryId: string
}

function getProductsQueryOptions(
  filters: ProductsFilters,
  pagination: PaginationState,
  search: string,
) {
  return {
    queryFn: () =>
      ProductsService.readProducts({
        skip: pagination.pageIndex * pagination.pageSize,
        limit: pagination.pageSize,
        productType: toProductType(filters.productType),
        categoryId:
          filters.categoryId === NONE ? undefined : filters.categoryId,
        name: search || undefined,
      }),
    queryKey: [
      "products",
      filters.productType,
      filters.categoryId,
      search,
      pagination,
    ],
  }
}

function ProductsTableContent({
  filters,
  pagination,
  setPagination,
  search,
}: {
  filters: ProductsFilters
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
  search: string
}) {
  const { data: products } = useSuspenseQuery(
    getProductsQueryOptions(filters, pagination, search),
  )

  return (
    <DataTable
      columns={columns}
      data={products.data}
      total={products.count}
      pagination={pagination}
      onPaginationChange={setPagination}
    />
  )
}

function ProductsTable({
  filters,
  pagination,
  setPagination,
  search,
}: {
  filters: ProductsFilters
  pagination: PaginationState
  setPagination: (pagination: PaginationState) => void
  search: string
}) {
  return (
    <Suspense fallback={<PendingProducts />}>
      <ProductsTableContent
        filters={filters}
        pagination={pagination}
        setPagination={setPagination}
        search={search}
      />
    </Suspense>
  )
}

export const Products = () => {
  const [filters, setFilters] = useState<ProductsFilters>({
    productType: NONE,
    categoryId: NONE,
  })
  const [searchInput, setSearchInput] = useState("")
  const search = useDebouncedValue(searchInput, SEARCH_DEBOUNCE_MS)
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 10,
  })
  const resetPage = () =>
    setPagination((current) => ({ ...current, pageIndex: 0 }))
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
          <div className="relative">
            <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchInput}
              onChange={(event) => {
                setSearchInput(event.target.value)
                resetPage()
              }}
              placeholder="搜索商品名称"
              className="w-52 pl-9"
            />
          </div>
          <Select
            value={filters.categoryId}
            onValueChange={(categoryId) => {
              setFilters((current) => ({ ...current, categoryId }))
              resetPage()
            }}
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
            onValueChange={(productType) => {
              setFilters((current) => ({ ...current, productType }))
              resetPage()
            }}
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
      <ProductsTable
        filters={filters}
        pagination={pagination}
        setPagination={setPagination}
        search={search}
      />
    </div>
  )
}
