import { useSuspenseQuery } from "@tanstack/react-query"
import { Suspense } from "react"

import { ImagesService } from "frontend/src/client"
import { DataTable } from "frontend/src/components/Common/DataTable"
import PendingCategories from "frontend/src/components/Pending/PendingCategories"
import { categoryColumns } from "./CategoryColumns"
import AddCategory from "./AddCategory"

function getCategoriesQueryOptions() {
  return {
    queryFn: () => ImagesService.readCategories(),
    queryKey: ["image-categories"],
  }
}

function CategoriesTableContent() {
  const { data: categories } = useSuspenseQuery(getCategoriesQueryOptions())

  return <DataTable columns={categoryColumns} data={categories.data} />
}

function CategoriesTable() {
  return (
    <Suspense fallback={<PendingCategories />}>
      <CategoriesTableContent />
    </Suspense>
  )
}

export const ImageCategories = () => {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">图片分类</h2>
          <p className="text-muted-foreground">
            管理图片分类的定义，包含排序、图标、启用状态等
          </p>
        </div>
        <AddCategory />
      </div>
      <CategoriesTable />
    </div>
  )
}
