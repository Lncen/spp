import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Tag } from "lucide-react"
import { useState } from "react"

import { ImagesService, type ImagePublic } from "@/client"
import { Button } from "@/components/ui/button"
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
import { Label } from "@/components/ui/label"
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

interface EditImageCategoryProps {
  image: ImagePublic
  onSuccess: () => void
}

const EditImageCategory = ({ image, onSuccess }: EditImageCategoryProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState(image.category ?? "")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: categoryOptions } = useQuery<string[]>({
    queryKey: ["image-category-options"],
    queryFn: () => ImagesService.readCategoryOptions(),
    staleTime: 5 * 60 * 1000,
    retry: false,
  })

  const mutation = useMutation({
    mutationFn: () =>
      ImagesService.updateImage({
        id: image.id,
        requestBody: {
          category: selectedCategory || null,
        },
      }),
    onSuccess: () => {
      showSuccessToast("图片分类已更新")
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries()
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    mutation.mutate()
  }

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      setSelectedCategory(image.category ?? "")
    }
    setIsOpen(open)
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DropdownMenuItem
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Tag />
        修改分类
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>修改图片分类</DialogTitle>
            <DialogDescription>
              为"{image.filename}"选择新的分类
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>分类</Label>
              <Select value={selectedCategory} onValueChange={setSelectedCategory}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="选择分类" />
                </SelectTrigger>
                <SelectContent>
                  {categoryOptions?.map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {opt}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>
                取消
              </Button>
            </DialogClose>
            <LoadingButton
              type="submit"
              loading={mutation.isPending}
              disabled={mutation.isPending}
            >
              保存
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default EditImageCategory