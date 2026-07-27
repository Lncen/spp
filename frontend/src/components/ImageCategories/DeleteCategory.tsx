import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"

import { ImagesService } from "frontend/src/client"
import { Button } from "frontend/src/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "frontend/src/components/ui/dialog"
import { DropdownMenuItem } from "frontend/src/components/ui/dropdown-menu"
import { LoadingButton } from "frontend/src/components/ui/loading-button"
import useCustomToast from "frontend/src/hooks/useCustomToast"
import { handleError } from "frontend/src/utils"

interface DeleteCategoryProps {
  id: string
  name: string
  onSuccess: () => void
}

const DeleteCategory = ({ id, name, onSuccess }: DeleteCategoryProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const { handleSubmit } = useForm()

  const deleteCategory = async (id: string) => {
    await ImagesService.deleteCategory({ id })
  }

  const mutation = useMutation({
    mutationFn: deleteCategory,
    onSuccess: () => {
      showSuccessToast("分类已删除")
      setIsOpen(false)
      onSuccess()
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["image-categories"] })
    },
  })

  const onSubmit = async () => {
    mutation.mutate(id)
  }

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuItem
        variant="destructive"
        onSelect={(e) => e.preventDefault()}
        onClick={() => setIsOpen(true)}
      >
        <Trash2 />
        删除分类
      </DropdownMenuItem>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit(onSubmit)}>
          <DialogHeader>
            <DialogTitle>删除分类</DialogTitle>
            <DialogDescription>
              确定要删除分类 "<strong>{name}</strong>" 吗？如有图片引用该分类，操作将被拒绝。
              此操作不可撤销。
            </DialogDescription>
          </DialogHeader>

          <DialogFooter className="mt-4">
            <DialogClose asChild>
              <Button variant="outline" disabled={mutation.isPending}>
                取消
              </Button>
            </DialogClose>
            <LoadingButton
              variant="destructive"
              type="submit"
              loading={mutation.isPending}
            >
              删除
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default DeleteCategory
