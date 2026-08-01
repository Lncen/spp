import { useSuspenseQuery } from "@tanstack/react-query"
import { Suspense } from "react"

import { ProductsService } from "@/client"
import { DataTable } from "@/components/Common/DataTable"
import AddProduct from "./AddProduct"
import { columns } from "./columns"
import PendingProducts from "./PendingProducts"

function getProductsQueryOptions() {
  return {
    queryFn: () => ProductsService.readProducts({ skip: 0, limit: 100 }),
    queryKey: ["products"],
  }
}

function ProductsTableContent() {
  const { data: products } = useSuspenseQuery(getProductsQueryOptions())

  return <DataTable columns={columns} data={products.data} />
}

function ProductsTable() {
  return (
    <Suspense fallback={<PendingProducts />}>
      <ProductsTableContent />
    </Suspense>
  )
}

export const Products = () => {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">商品管理</h2>
          <p className="text-muted-foreground">
            管理商品信息、定价、库存与履约配置
          </p>
        </div>
        <AddProduct />
      </div>
      <ProductsTable />
    </div>
  )
}
