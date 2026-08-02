import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Image, ListFilter } from "lucide-react"
import { useState } from "react"
import { ImageCategoriesService, ImagesService } from "@/client"
import { ImageCard } from "@/components/Admin/Images/ImageCard"
import UploadImage from "@/components/Admin/Images/UploadImage"
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const PAGE_SIZE = 12
function getImagesQueryOptions(skip: number, limit: number, category?: string) {
  return {
    queryKey: ["images", { skip, limit, category }],
    queryFn: () => ImagesService.readImages({ skip, limit, category }),
  }
}
export const Route = createFileRoute("/_layout/images")({
  component: Images,
  head: () => ({
    meta: [{ title: "Images - FastAPI Template" }],
  }),
})
function getPageNumbers(currentPage: number, totalPages: number) {
  const pages: (number | "ellipsis")[] = []
  const maxVisible = 5
  if (totalPages <= maxVisible + 2) {
    for (let i = 1; i <= totalPages; i++) pages.push(i)
  } else {
    pages.push(1)
    const start = Math.max(2, currentPage - 1)
    const end = Math.min(totalPages - 1, currentPage + 1)
    if (start > 2) pages.push("ellipsis")
    for (let i = start; i <= end; i++) pages.push(i)
    if (end < totalPages - 1) pages.push("ellipsis")
    pages.push(totalPages)
  }
  return pages
}
function CategoryFilter({
  options,
  value,
  onChange,
}: {
  options?: string[]
  value: string
  onChange: (value: string) => void
}) {
  const selectValue = value || "all"
  return (
    <div className="flex items-center gap-3">
      <ListFilter className="size-4 text-muted-foreground shrink-0" />
      <Select
        value={selectValue}
        onValueChange={(v) => onChange(v === "all" ? "" : v)}
      >
        <SelectTrigger className="w-44 h-9">
          <SelectValue placeholder="全部分类">
            {selectValue === "all" ? "全部分类" : value}
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">全部分类</SelectItem>
          {options?.map((opt) => (
            <SelectItem key={opt} value={opt}>
              {opt}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
function Images() {
  const [currentPage, setCurrentPage] = useState(1)
  const [category, setCategory] = useState("")
  const skip = (currentPage - 1) * PAGE_SIZE
  const { data: imagesData, isPending } = useQuery(
    getImagesQueryOptions(skip, PAGE_SIZE, category || undefined),
  )
  const { data: categoryOptions } = useQuery<string[]>({
    queryKey: ["image-category-options"],
    queryFn: () => ImageCategoriesService.readCategoryOptions(),
    staleTime: 5 * 60 * 1000,
    retry: false,
  })
  const images = imagesData?.data ?? []
  const totalCount = imagesData?.count ?? 0
  const totalPages = Math.ceil(totalCount / PAGE_SIZE)
  const handleCategoryChange = (value: string) => {
    setCategory(value)
    setCurrentPage(1)
  }
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">图片管理</h1>
          <p className="text-muted-foreground">上传和管理你的图片资源</p>
        </div>
        <UploadImage />
      </div>
      <CategoryFilter
        options={categoryOptions}
        value={category}
        onChange={handleCategoryChange}
      />
      {isPending ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
          {Array.from({ length: PAGE_SIZE }).map((_, i) => (
            <div
              key={i}
              className="aspect-[4/3] rounded-xl bg-muted animate-pulse"
            />
          ))}
        </div>
      ) : images.length === 0 ? (
        <div className="flex flex-col items-center justify-center text-center py-12">
          <div className="rounded-full bg-muted p-4 mb-4">
            <Image className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold">还没有图片</h3>
          <p className="text-muted-foreground">
            {category ? "当前分类没有图片" : "上传一张图片开始使用"}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
            {images.map((image) => (
              <ImageCard key={image.id} image={image} />
            ))}
          </div>
          {totalPages > 1 && (
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    href="#"
                    onClick={(e) => {
                      e.preventDefault()
                      if (currentPage > 1) setCurrentPage((p) => p - 1)
                    }}
                    className={
                      currentPage <= 1 ? "pointer-events-none opacity-50" : ""
                    }
                  />
                </PaginationItem>
                {getPageNumbers(currentPage, totalPages).map((page, i) =>
                  page === "ellipsis" ? (
                    <PaginationItem key={`e-${i}`}>
                      <PaginationEllipsis />
                    </PaginationItem>
                  ) : (
                    <PaginationItem key={page}>
                      <PaginationLink
                        href="#"
                        isActive={page === currentPage}
                        onClick={(e) => {
                          e.preventDefault()
                          setCurrentPage(page)
                        }}
                      >
                        {page}
                      </PaginationLink>
                    </PaginationItem>
                  ),
                )}
                <PaginationItem>
                  <PaginationNext
                    href="#"
                    onClick={(e) => {
                      e.preventDefault()
                      if (currentPage < totalPages) setCurrentPage((p) => p + 1)
                    }}
                    className={
                      currentPage >= totalPages
                        ? "pointer-events-none opacity-50"
                        : ""
                    }
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          )}
        </div>
      )}
    </div>
  )
}
