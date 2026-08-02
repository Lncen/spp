import { useSuspenseQuery } from "@tanstack/react-query"
import { Suspense } from "react"

import { ImageCategoriesService } from "@/client"
import PendingCategories from "@/components/Admin/Pending/PendingCategories"
import { DataTable } from "@/components/Common/DataTable"
import AddCategory from "./AddCategory"
import { categoryColumns } from "./CategoryColumns"

function getCategoriesQueryOptions() {
  return {
    queryFn: () => ImageCategoriesService.readCategories(),
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
