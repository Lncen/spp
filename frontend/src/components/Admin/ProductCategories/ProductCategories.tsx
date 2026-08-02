import { useSuspenseQuery } from "@tanstack/react-query"
import { Suspense, useMemo } from "react"

import { ProductCategoriesService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import AddProductCategory from "./AddProductCategory"
import PendingProductCategories from "./PendingProductCategories"
import { createProductCategoryColumns } from "./ProductCategoryColumns"
import { toProductCategoryRows } from "./types"

function getProductCategoriesQueryOptions() {
  return {
    queryFn: () => ProductCategoriesService.readProductCategories(),
    queryKey: ["product-categories"],
  }
}

function ProductCategoriesTableContent() {
  const { data: categories } = useSuspenseQuery(
    getProductCategoriesQueryOptions(),
  )
  const columns = useMemo(() => createProductCategoryColumns(), [])
  const rows = useMemo(
    () => toProductCategoryRows(categories.data),
    [categories],
  )

  return <DataTable columns={columns} data={rows} />
}

function ProductCategoriesTable() {
  return (
    <Suspense fallback={<PendingProductCategories />}>
      <ProductCategoriesTableContent />
    </Suspense>
  )
}

export const ProductCategories = () => {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">商品分类</h2>
          <p className="text-muted-foreground">
            管理商品分类的层级、图标、排序与启用状态
          </p>
        </div>
        <AddProductCategory />
      </div>
      <ProductCategoriesTable />
    </div>
  )
}
