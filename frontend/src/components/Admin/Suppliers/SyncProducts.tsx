import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { RefreshCw } from "lucide-react"
import { useState } from "react"

import type {
  ProductCategoryTreePublic,
  TaskStatusPublic,
  UpstreamCategoryPublic,
} from "@/client"
import { ProductCategoriesService, SuppliersService } from "@/client"
import { Badge } from "@/components/ui/badge"
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
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

interface SyncProductsProps {
  id: string
}

interface SyncTaskResult {
  created?: string[]
  updated?: string[]
  failed?: Array<{ product_id: string; error: string }>
}

const PENDING_STATUSES = new Set(["PENDING", "STARTED", "RETRY"])

const sleep = (ms: number) =>
  new Promise<void>((resolve) => setTimeout(resolve, ms))

interface CategoryOption {
  id: string
  name: string
  depth: number
}

interface LocalCategoryOption {
  id: string
  name: string
  depth: number
}

const buildCategoryOptions = (
  categories: UpstreamCategoryPublic[],
): CategoryOption[] => {
  const childrenMap = new Map<string | null, UpstreamCategoryPublic[]>()
  for (const category of categories) {
    const parentId =
      category.parent_id && category.parent_id !== "0"
        ? category.parent_id
        : null
    const siblings = childrenMap.get(parentId) ?? []
    siblings.push(category)
    childrenMap.set(parentId, siblings)
  }

  const options: CategoryOption[] = []
  const visit = (parentId: string | null, depth: number) => {
    for (const category of childrenMap.get(parentId) ?? []) {
      options.push({ id: category.id, name: category.name, depth })
      visit(category.id, depth + 1)
    }
  }
  visit(null, 0)
  return options
}

const buildLocalCategoryOptions = (
  categories: ProductCategoryTreePublic[],
  depth = 0,
  options: LocalCategoryOption[] = [],
): LocalCategoryOption[] => {
  for (const category of categories) {
    options.push({ id: category.id, name: category.name, depth })
    buildLocalCategoryOptions(category.children ?? [], depth + 1, options)
  }
  return options
}

const SyncProducts = ({ id }: SyncProductsProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [result, setResult] = useState<SyncTaskResult | null>(null)
  const [categoryId, setCategoryId] = useState("")
  const [localCategoryId, setLocalCategoryId] = useState("")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: categoriesData } = useQuery({
    queryKey: ["supplier-upstream-categories", id],
    queryFn: () => SuppliersService.readUpstreamCategories({ id }),
    enabled: isOpen,
    retry: false,
  })

  const { data: localCategoriesData } = useQuery({
    queryKey: ["product-categories"],
    queryFn: () => ProductCategoriesService.readProductCategories(),
    enabled: isOpen,
    retry: false,
  })

  const {
    data: productsData,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["supplier-upstream-products", id, categoryId],
    queryFn: () =>
      SuppliersService.readUpstreamProducts({
        id,
        categoryId: categoryId === "" ? undefined : categoryId,
      }),
    enabled: isOpen && categoryId !== "",
    retry: false,
  })

  const categories = categoriesData?.data ?? []
  const categoryOptions = buildCategoryOptions(categories)
  const localCategoryOptions = buildLocalCategoryOptions(
    localCategoriesData?.data ?? [],
  )
  const products = productsData?.data ?? []
  const selectedCount = selected.size
  const allChecked =
    products.length > 0 &&
    products.every((product) => selected.has(product.upstream_id))
  const someChecked = products.some((product) =>
    selected.has(product.upstream_id),
  )

  const openDialog = () => {
    setCategoryId("")
    setLocalCategoryId("")
    setSelected(new Set())
    setResult(null)
    setIsOpen(true)
  }

  const changeCategory = (value: string) => {
    setSelected(new Set())
    setResult(null)
    setCategoryId(value)
  }

  const toggleProduct = (productId: string, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (checked) {
        next.add(productId)
      } else {
        next.delete(productId)
      }
      return next
    })
  }

  const toggleAll = (checked: boolean) => {
    setSelected(
      checked
        ? new Set(products.map((product) => product.upstream_id))
        : new Set(),
    )
  }

  const mutation = useMutation({
    mutationFn: async (): Promise<TaskStatusPublic> => {
      const sync = await SuppliersService.createUpstreamProductsSync({
        id,
        requestBody: {
          product_ids: Array.from(selected),
          category_id:
            localCategoryId === "" ? undefined : localCategoryId,
        },
      })
      for (let attempt = 0; attempt < 120; attempt += 1) {
        await sleep(1500)
        const status = await SuppliersService.readUpstreamProductsSyncStatus({
          id,
          taskId: sync.task_id,
        })
        if (!PENDING_STATUSES.has(status.status)) {
          return status
        }
      }
      return { status: "TIMEOUT", success: false }
    },
    onSuccess: (status) => {
      if (status.status === "TIMEOUT") {
        showErrorToast("同步任务超时，请稍后到商品列表确认结果")
        return
      }
      if (!status.success) {
        showErrorToast(`同步任务失败：${status.status}`)
        return
      }
      const taskResult = (status.result ??
        null) as unknown as SyncTaskResult | null
      setResult(taskResult)
      showSuccessToast(
        `同步完成：创建 ${taskResult?.created?.length ?? 0}，更新 ${taskResult?.updated?.length ?? 0}，失败 ${taskResult?.failed?.length ?? 0}`,
      )
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["suppliers"] })
      queryClient.invalidateQueries({ queryKey: ["products"] })
      queryClient.invalidateQueries({ queryKey: ["product-categories"] })
      queryClient.invalidateQueries({
        queryKey: ["supplier-upstream-products", id],
      })
    },
  })

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!mutation.isPending) {
          setIsOpen(open)
        }
      }}
    >
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={openDialog}
      >
        <RefreshCw />
        同步商品
      </DropdownMenuItem>
      <DialogContent
        className="sm:max-w-xl"
        showCloseButton={!mutation.isPending}
      >
        <DialogHeader>
          <DialogTitle>同步上游商品</DialogTitle>
          <DialogDescription>
            勾选要同步的商品。已匹配的本地商品只更新成本价，未匹配的会自动创建。
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2">
          <span className="shrink-0 text-sm text-muted-foreground">分类</span>
          <Select value={categoryId} onValueChange={changeCategory}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="请选择分类" />
            </SelectTrigger>
            <SelectContent>
              {categoryOptions.map((category) => (
                <SelectItem key={category.id} value={category.id}>
                  {category.depth > 0 ? "　".repeat(category.depth) : ""}
                  {category.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <span className="shrink-0 text-sm text-muted-foreground">本地分类</span>
          <Select value={localCategoryId} onValueChange={setLocalCategoryId}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="不修改分类" />
            </SelectTrigger>
            <SelectContent>
              {localCategoryOptions.map((category) => (
                <SelectItem key={category.id} value={category.id}>
                  {category.depth > 0 ? "　".repeat(category.depth) : ""}
                  {category.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="max-h-[55vh] space-y-1 overflow-y-auto pr-1 [scrollbar-color:var(--border)_transparent] [&::-webkit-scrollbar-track]:bg-transparent">
          {!categoryId ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              请选择分类后加载商品
            </div>
          ) : isLoading ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              正在获取上游商品列表...
            </div>
          ) : isError ? (
            <div className="py-10 text-center text-sm text-destructive">
              获取上游商品列表失败
            </div>
          ) : products.length === 0 ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              暂无上游商品
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2 rounded-md border px-2 py-1.5">
                <Checkbox
                  checked={
                    allChecked ? true : someChecked ? "indeterminate" : false
                  }
                  onCheckedChange={(checked) => toggleAll(checked === true)}
                />
                <span className="text-sm font-medium">全选</span>
                <span className="ml-auto text-xs text-muted-foreground">
                  已选 {selectedCount}/{products.length}
                </span>
              </div>
              {products.map((product) => (
                <div
                  key={product.upstream_id}
                  className="flex items-center gap-2 rounded-md border px-2 py-2 hover:bg-muted/50"
                >
                  <Checkbox
                    checked={selected.has(product.upstream_id)}
                    onCheckedChange={(checked) =>
                      toggleProduct(product.upstream_id, checked === true)
                    }
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">
                      {product.name}
                    </span>
                    <span className="block truncate text-xs text-muted-foreground">
                      ID: {product.upstream_id}
                    </span>
                  </span>
                  {product.cost_price != null && (
                    <span className="font-mono text-xs">
                      {product.cost_price}
                    </span>
                  )}
                  <Badge
                    variant={product.synced ? "secondary" : "outline"}
                    className="shrink-0"
                  >
                    {product.synced ? "已同步" : "未同步"}
                  </Badge>
                </div>
              ))}
            </>
          )}
        </div>

        {result && (
          <div className="rounded-md border bg-muted/40 p-3 text-sm">
            <div className="flex gap-4">
              <span>
                创建 <strong>{result.created?.length ?? 0}</strong>
              </span>
              <span>
                更新 <strong>{result.updated?.length ?? 0}</strong>
              </span>
              <span className={cn(result.failed?.length && "text-destructive")}>
                失败 <strong>{result.failed?.length ?? 0}</strong>
              </span>
            </div>
            {result.failed && result.failed.length > 0 && (
              <ul className="mt-2 max-h-24 space-y-1 overflow-y-auto text-xs text-muted-foreground [scrollbar-color:var(--border)_transparent] [&::-webkit-scrollbar-track]:bg-transparent">
                {result.failed.map((item) => (
                  <li key={item.product_id}>
                    ID {item.product_id}：{item.error}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={mutation.isPending}>
              取消
            </Button>
          </DialogClose>
          <LoadingButton
            type="button"
            loading={mutation.isPending}
            disabled={selectedCount === 0 || isError || isLoading}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? "同步中..." : `同步所选 (${selectedCount})`}
          </LoadingButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default SyncProducts
