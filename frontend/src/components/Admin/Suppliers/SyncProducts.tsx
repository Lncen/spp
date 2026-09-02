import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  ChevronDown,
  ChevronRight,
  Folder,
  FolderTree,
  RefreshCw,
  Search,
} from "lucide-react"
import { type CSSProperties, useMemo, useState } from "react"

import type {
  ProductCategoryTreePublic,
  TaskStatusPublic,
  UpstreamCategoryPublic,
} from "@/client"
import { ProductCategoriesService, SuppliersService } from "@/client"
import { Badge } from "@/components/ui/badge"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
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
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInput,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarProvider,
} from "@/components/ui/sidebar"
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

interface CategoryNode {
  id: string
  name: string
  parentId: string
  children: CategoryNode[]
}

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

const buildCategoryTree = (
  categories: UpstreamCategoryPublic[],
): CategoryNode[] => {
  const nodes = new Map<string, CategoryNode>()
  for (const category of categories) {
    nodes.set(category.id, {
      id: category.id,
      name: category.name,
      parentId:
        category.parent_id && category.parent_id !== "0"
          ? category.parent_id
          : "",
      children: [],
    })
  }
  const roots: CategoryNode[] = []
  for (const node of nodes.values()) {
    const parent = node.parentId ? nodes.get(node.parentId) : undefined
    if (parent) {
      parent.children.push(node)
    } else {
      roots.push(node)
    }
  }
  return roots
}

const filterCategoryTree = (
  nodes: CategoryNode[],
  keyword: string,
): CategoryNode[] => {
  const query = keyword.trim().toLowerCase()
  if (!query) {
    return nodes
  }
  const result: CategoryNode[] = []
  for (const node of nodes) {
    const children = filterCategoryTree(node.children, query)
    if (node.name.toLowerCase().includes(query) || children.length > 0) {
      result.push({ ...node, children })
    }
  }
  return result
}

const flattenCategoryTree = (
  nodes: CategoryNode[],
  depth = 0,
  options: CategoryOption[] = [],
): CategoryOption[] => {
  for (const node of nodes) {
    options.push({ id: node.id, name: node.name, depth })
    flattenCategoryTree(node.children, depth + 1, options)
  }
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

interface CategoryTreeItemProps {
  node: CategoryNode
  depth: number
  activeId: string
  expandedIds: Set<string>
  forceExpand: boolean
  onSelect: (id: string) => void
  onToggleExpand: (id: string, open: boolean) => void
}

const CategoryTreeItem = ({
  node,
  depth,
  activeId,
  expandedIds,
  forceExpand,
  onSelect,
  onToggleExpand,
}: CategoryTreeItemProps) => {
  const hasChildren = node.children.length > 0
  const isExpanded = forceExpand || expandedIds.has(node.id)

  return (
    <SidebarMenuItem>
      <Collapsible
        open={isExpanded}
        onOpenChange={(open) => onToggleExpand(node.id, open)}
      >
        <CollapsibleTrigger asChild>
          <SidebarMenuButton
            isActive={activeId === node.id}
            onClick={() => onSelect(node.id)}
            className={cn("pr-8", depth > 0 && "pl-8")}
          >
            <Folder />
            <span className="truncate">{node.name}</span>
            {hasChildren &&
              (isExpanded ? (
                <ChevronDown className="ml-auto shrink-0" />
              ) : (
                <ChevronRight className="ml-auto shrink-0" />
              ))}
          </SidebarMenuButton>
        </CollapsibleTrigger>
        {hasChildren && (
          <CollapsibleContent>
            <SidebarMenuSub>
              {node.children.map((child) => (
                <CategoryTreeItem
                  key={child.id}
                  node={child}
                  depth={depth + 1}
                  activeId={activeId}
                  expandedIds={expandedIds}
                  forceExpand={forceExpand}
                  onSelect={onSelect}
                  onToggleExpand={onToggleExpand}
                />
              ))}
            </SidebarMenuSub>
          </CollapsibleContent>
        )}
      </Collapsible>
    </SidebarMenuItem>
  )
}

const SyncProducts = ({ id }: SyncProductsProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [result, setResult] = useState<SyncTaskResult | null>(null)
  const [categoryId, setCategoryId] = useState("")
  const [localCategoryId, setLocalCategoryId] = useState("")
  const [search, setSearch] = useState("")
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
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
  const categoryNodes = useMemo(
    () => buildCategoryTree(categories),
    [categories],
  )
  const categoryById = useMemo(() => {
    const map = new Map<string, CategoryNode>()
    const visit = (nodes: CategoryNode[]) => {
      for (const node of nodes) {
        map.set(node.id, node)
        visit(node.children)
      }
    }
    visit(categoryNodes)
    return map
  }, [categoryNodes])
  const filteredCategoryNodes = useMemo(
    () => filterCategoryTree(categoryNodes, search),
    [categoryNodes, search],
  )
  const categoryOptions = useMemo(
    () => flattenCategoryTree(categoryNodes),
    [categoryNodes],
  )
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
  const selectedCategoryPath = useMemo(() => {
    if (!categoryId) {
      return []
    }
    const path: CategoryNode[] = []
    let current = categoryById.get(categoryId)
    while (current) {
      path.unshift(current)
      current = current.parentId
        ? categoryById.get(current.parentId)
        : undefined
    }
    return path
  }, [categoryId, categoryById])

  const openDialog = () => {
    setCategoryId("")
    setLocalCategoryId("")
    setSelected(new Set())
    setResult(null)
    setSearch("")
    setExpandedIds(new Set())
    setIsOpen(true)
  }

  const toggleExpand = (nodeId: string, open: boolean) => {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (open) {
        next.add(nodeId)
      } else {
        next.delete(nodeId)
      }
      return next
    })
  }

  const selectCategory = (value: string) => {
    setSelected(new Set())
    setResult(null)
    setCategoryId(value)
    setExpandedIds((prev) => {
      const next = new Set(prev)
      next.add(value)
      let parent = categoryById.get(value)?.parentId
      while (parent) {
        next.add(parent)
        parent = categoryById.get(parent)?.parentId
      }
      return next
    })
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

  const handleSync = () => {
    if (!localCategoryId) {
      showErrorToast("请先选择本地分类")
      return
    }
    mutation.mutate()
  }

  const mutation = useMutation({
    mutationFn: async (): Promise<TaskStatusPublic> => {
      const sync = await SuppliersService.createUpstreamProductsSync({
        id,
        requestBody: {
          product_ids: Array.from(selected),
          category_id: localCategoryId === "" ? undefined : localCategoryId,
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
        className="gap-0 overflow-hidden p-0 sm:max-w-2xl md:max-h-[820px] md:max-w-[960px] lg:max-w-[1120px]"
        showCloseButton={!mutation.isPending}
      >
        <DialogHeader className="px-6 pt-6">
          <DialogTitle>同步上游商品</DialogTitle>
          <DialogDescription>
            勾选要同步的商品。已匹配的本地商品更新成本价与关闭状态，未匹配的会自动创建。
          </DialogDescription>
        </DialogHeader>

        <SidebarProvider
          className="overflow-hidden"
          style={
            {
              "--sidebar-width": "25rem",
              minHeight: 0,
              height: "min(680px, 78vh)",
            } as CSSProperties
          }
        >
          <Sidebar
            collapsible="none"
            className="hidden border-r md:flex"
            style={{ backgroundColor: "transparent" }}
          >
            <SidebarHeader>
              <div className="relative">
                <Search className="text-muted-foreground absolute top-1/2 left-2.5 size-4 -translate-y-1/2" />
                <SidebarInput
                  placeholder="搜索分类"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  className="pl-8"
                />
              </div>
            </SidebarHeader>
            <SidebarContent>
              <SidebarGroup>
                <SidebarGroupLabel>
                  <FolderTree />
                  上游分类
                </SidebarGroupLabel>
                <SidebarGroupContent>
                  {!categoriesData ? (
                    <p className="px-2 py-4 text-center text-sm text-muted-foreground">
                      正在加载分类…
                    </p>
                  ) : filteredCategoryNodes.length === 0 ? (
                    <p className="px-2 py-4 text-center text-sm text-muted-foreground">
                      {categories.length === 0 ? "暂无分类" : "无匹配分类"}
                    </p>
                  ) : (
                    <SidebarMenu>
                      {filteredCategoryNodes.map((node) => (
                        <CategoryTreeItem
                          key={node.id}
                          node={node}
                          depth={0}
                          activeId={categoryId}
                          expandedIds={expandedIds}
                          forceExpand={search.trim() !== ""}
                          onSelect={selectCategory}
                          onToggleExpand={toggleExpand}
                        />
                      ))}
                    </SidebarMenu>
                  )}
                </SidebarGroupContent>
              </SidebarGroup>
            </SidebarContent>
          </Sidebar>

          <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
            <header className="flex shrink-0 flex-wrap items-center gap-2 border-b px-4 py-2">
              <Breadcrumb className="min-w-0 flex-1">
                <BreadcrumbList>
                  {selectedCategoryPath.length === 0 ? (
                    <BreadcrumbItem>
                      <BreadcrumbPage>请选择分类</BreadcrumbPage>
                    </BreadcrumbItem>
                  ) : (
                    selectedCategoryPath.map((item, index) => {
                      const isLast = index === selectedCategoryPath.length - 1
                      return (
                        <BreadcrumbItem key={item.id} className="min-w-0">
                          {isLast ? (
                            <BreadcrumbPage className="truncate">
                              {item.name}
                            </BreadcrumbPage>
                          ) : (
                            <>
                              <BreadcrumbLink asChild>
                                <button
                                  type="button"
                                  onClick={() => selectCategory(item.id)}
                                  className="truncate"
                                >
                                  {item.name}
                                </button>
                              </BreadcrumbLink>
                              <BreadcrumbSeparator />
                            </>
                          )}
                        </BreadcrumbItem>
                      )
                    })
                  )}
                </BreadcrumbList>
              </Breadcrumb>
              <div className="flex items-center gap-2">
                <span className="shrink-0 text-sm text-muted-foreground">
                  本地分类
                </span>
                <Select
                  value={localCategoryId}
                  onValueChange={setLocalCategoryId}
                >
                  <SelectTrigger className="w-44">
                    <SelectValue placeholder="请选择本地分类" />
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
            </header>

            <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
              <div className="flex items-center gap-2 md:hidden">
                <span className="shrink-0 text-sm text-muted-foreground">
                  分类
                </span>
                <Select value={categoryId} onValueChange={selectCategory}>
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
                        allChecked
                          ? true
                          : someChecked
                            ? "indeterminate"
                            : false
                      }
                      onCheckedChange={(checked) => toggleAll(checked === true)}
                    />
                    <span className="text-sm font-medium">全选</span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      已选 {selectedCount}/{products.length}
                    </span>
                  </div>
                  <div className="flex flex-col gap-1">
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
                          variant="outline"
                          className={cn(
                            "shrink-0",
                            product.synced && "border-green-500 text-green-700",
                          )}
                        >
                          {product.synced ? "已同步" : "未同步"}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            <footer className="flex shrink-0 items-center justify-end gap-2 border-t px-4 py-3">
              {result && (
                <div className="rounded-md border bg-muted/40 p-3 text-sm text-left">
                  <div className="flex gap-4 ">
                    <span>
                      创建 <strong>{result.created?.length ?? 0}</strong>
                    </span>
                    <span>
                      更新 <strong>{result.updated?.length ?? 0}</strong>
                    </span>
                    <span
                      className={cn(
                        result.failed?.length && "text-destructive",
                      )}
                    >
                      失败 <strong>{result.failed?.length ?? 0}</strong>
                    </span>
                  </div>
                  {result.failed && result.failed.length > 0 && (
                    <ul className="mt-2 max-h-24 space-y-1 overflow-y-auto text-xs text-muted-foreground">
                      {result.failed.map((item) => (
                        <li key={item.product_id}>
                          ID {item.product_id}：{item.error}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  取消
                </Button>
              </DialogClose>
              <LoadingButton
                type="button"
                loading={mutation.isPending}
                disabled={selectedCount === 0 || isError || isLoading}
                onClick={handleSync}
              >
                {mutation.isPending
                  ? "同步中..."
                  : `同步所选 (${selectedCount})`}
              </LoadingButton>
            </footer>
          </main>
        </SidebarProvider>
      </DialogContent>
    </Dialog>
  )
}

export default SyncProducts
