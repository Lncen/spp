import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useMemo } from "react"
import { useForm } from "react-hook-form"

import type { ProductCategoryPublic } from "@/client"
import { ImagesService, ProductCategoriesService } from "@/client"
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
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import {
  flattenProductCategories,
  getProductCategoryPath,
  type ProductCategoryFormValues,
  productCategoryFormSchema,
  toProductCategoryCreate,
  toProductCategoryFormValues,
  toProductCategoryUpdate,
} from "./types"

interface ProductCategoryFormDialogProps {
  category?: ProductCategoryPublic
  isOpen: boolean
  onOpenChange: (open: boolean) => void
  onSuccess?: () => void
}

function getDescendantIds(
  categories: ProductCategoryPublic[],
  categoryId: string,
): string[] {
  return categories
    .filter((category) => category.parent_id === categoryId)
    .flatMap((category) => [
      category.id,
      ...getDescendantIds(categories, category.id),
    ])
}

const ProductCategoryFormDialog = ({
  category,
  isOpen,
  onOpenChange,
  onSuccess,
}: ProductCategoryFormDialogProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const isEdit = Boolean(category)

  const { data: categories } = useQuery({
    queryKey: ["product-categories"],
    queryFn: () => ProductCategoriesService.readProductCategories(),
  })
  const { data: images } = useQuery({
    queryKey: ["images"],
    queryFn: () => ImagesService.readImages({ skip: 0, limit: 200 }),
  })

  const excludedIds = useMemo(() => {
    if (!category) return new Set<string>()
    const flatCategories = flattenProductCategories(categories?.data ?? [])
    return new Set([
      category.id,
      ...getDescendantIds(flatCategories, category.id),
    ])
  }, [categories, category])

  const form = useForm<ProductCategoryFormValues>({
    resolver: zodResolver(productCategoryFormSchema) as any,
    mode: "onBlur",
    criteriaMode: "all",
    defaultValues: toProductCategoryFormValues(category),
  })

  useEffect(() => {
    if (isOpen) {
      form.reset(toProductCategoryFormValues(category))
    }
  }, [category, form, isOpen])

  const mutation = useMutation({
    mutationFn: (values: ProductCategoryFormValues) =>
      category
        ? ProductCategoriesService.updateProductCategory({
            categoryId: category.id,
            requestBody: toProductCategoryUpdate(values),
          })
        : ProductCategoriesService.createProductCategory({
            requestBody: toProductCategoryCreate(values),
          }),
    onSuccess: (data) => {
      showSuccessToast(`商品分类 "${data.name}" 已${isEdit ? "更新" : "创建"}`)
      form.reset()
      onOpenChange(false)
      onSuccess?.()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["product-categories"] })
      queryClient.invalidateQueries({ queryKey: ["products"] })
    },
  })

  const onSubmit = (values: ProductCategoryFormValues) => {
    mutation.mutate(values)
  }

  const parentOptions = useMemo(
    () =>
      flattenProductCategories(categories?.data ?? []).filter(
        (item) => !excludedIds.has(item.id),
      ),
    [categories, excludedIds],
  )

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{isEdit ? "编辑商品分类" : "添加商品分类"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "更新商品分类的名称、层级、图标与状态"
              : "创建一个新的商品分类"}
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <div className="grid gap-4 py-2">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      分类名称 <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="例如：代练服务" {...field} required />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="parentId"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>上级分类</FormLabel>
                      <Select
                        value={field.value ?? "none"}
                        onValueChange={(value) =>
                          field.onChange(value === "none" ? null : value)
                        }
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="选择上级分类" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="none">顶级分类</SelectItem>
                          {parentOptions.map((item) => (
                            <SelectItem key={item.id} value={item.id}>
                              {getProductCategoryPath(
                                categories?.data ?? [],
                                item.id,
                              ) ?? item.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="iconId"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>分类图标</FormLabel>
                      <Select
                        value={field.value ?? "none"}
                        onValueChange={(value) =>
                          field.onChange(value === "none" ? null : value)
                        }
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="选择图标" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="none">无图标</SelectItem>
                          {images?.data.map((image) => (
                            <SelectItem key={image.id} value={image.id}>
                              <span className="flex items-center gap-2">
                                <img
                                  src={image.url}
                                  alt=""
                                  className="size-5 rounded object-cover"
                                />
                                {image.filename}
                              </span>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <div className="grid grid-cols-2 items-end gap-4">
                <FormField
                  control={form.control}
                  name="sort"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>排序</FormLabel>
                      <FormControl>
                        <Input
                          type="number"
                          min={0}
                          placeholder="0"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="isActive"
                  render={({ field }) => (
                    <FormItem className="flex items-center gap-3 space-y-0 pb-1">
                      <FormControl>
                        <Checkbox
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                      <FormLabel className="font-normal">启用</FormLabel>
                    </FormItem>
                  )}
                />
              </div>
            </div>

            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  取消
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                {isEdit ? "保存" : "创建"}
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default ProductCategoryFormDialog
