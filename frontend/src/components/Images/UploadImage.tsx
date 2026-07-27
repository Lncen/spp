import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Upload } from "lucide-react"
import { useState } from "react"

import { ImagesService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
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

const UploadImage = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [category, setCategory] = useState("")
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data: categoryOptions } = useQuery<string[]>({
    queryKey: ["image-category-options"],
    queryFn: () => ImagesService.readCategoryOptions(),
    staleTime: 5 * 60 * 1000,
    retry: false,
  })

  const mutation = useMutation({
    mutationFn: (file: File) =>
      ImagesService.uploadImage({
        formData: { file: file as unknown as string },
        category: category || undefined,
      }),
    onSuccess: (data) => {
      showSuccessToast(`"${data.filename}" 上传成功`)
      setFile(null)
      setPreview(null)
      setCategory("")
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["images"] })
    },
  })

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0]
    if (!selected) {
      setFile(null)
      setPreview(null)
      return
    }
    setFile(selected)
    const url = URL.createObjectURL(selected)
    setPreview(url)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) return
    mutation.mutate(file)
  }

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      setFile(null)
      setPreview(null)
      setCategory("")
    }
    setIsOpen(open)
  }

  const acceptedFormats = ".jpg,.jpeg,.png,.webp"

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button className="my-4">
          <Upload className="mr-2" />
          上传图片
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>上传图片</DialogTitle>
            <DialogDescription>
              支持 JPEG、PNG、WebP 格式。
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="file">选择文件</Label>
              <Input
                id="file"
                type="file"
                accept={acceptedFormats}
                onChange={handleFileChange}
                required
              />
            </div>
            {preview && file && (
              <div className="flex flex-col items-center gap-2">
                <img
                  src={preview}
                  alt={file.name}
                  className="max-h-48 w-full rounded-md object-contain border"
                />
                <p className="text-xs text-muted-foreground">
                  {file.name} ({(file.size / 1024).toFixed(1)} KB)
                </p>
              </div>
            )}

            <div className="grid gap-2">
              <Label>分类</Label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="选择分类（可选）" />
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
              disabled={!file || mutation.isPending}
            >
              上传
            </LoadingButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export default UploadImage
