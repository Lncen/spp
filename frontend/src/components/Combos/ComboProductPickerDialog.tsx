import { useEffect, useRef, useState } from "react"

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
import { Separator } from "@/components/ui/separator"

export interface ComboProductCandidate {
  id: string
  name: string
  imageUrl: string | null | undefined
}

interface ComboProductPickerDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  candidates: ComboProductCandidate[]
  selectedIds: string[]
  onConfirm: (productIds: string[]) => void
}

/**
 * 商品选择弹窗：从收藏候选中勾选商品，确定后回写组合编辑弹窗，避免长列表挤占编辑信息。
 */
export const ComboProductPickerDialog = ({
  open,
  onOpenChange,
  candidates,
  selectedIds,
  onConfirm,
}: ComboProductPickerDialogProps) => {
  const [draftIds, setDraftIds] = useState<string[]>([])

  // 仅在打开时同步主弹窗的已选商品，避免编辑弹窗重渲染时覆盖弹窗内的临时勾选
  const selectedIdsRef = useRef(selectedIds)
  selectedIdsRef.current = selectedIds
  useEffect(() => {
    if (open) setDraftIds(selectedIdsRef.current)
  }, [open])

  const selectedSet = new Set(draftIds)
  const allSelected =
    candidates.length > 0 && draftIds.length === candidates.length

  const toggleProduct = (productId: string, checked: boolean) => {
    setDraftIds((current) =>
      checked
        ? current.includes(productId)
          ? current
          : [...current, productId]
        : current.filter((id) => id !== productId),
    )
  }

  const toggleAll = () => {
    setDraftIds(allSelected ? [] : candidates.map((candidate) => candidate.id))
  }

  const handleConfirm = () => {
    onConfirm(draftIds)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>选择商品</DialogTitle>
          <DialogDescription>
            从我的收藏中勾选商品，确定后回到组合编辑。
          </DialogDescription>
        </DialogHeader>
        <Separator />
        {candidates.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            收藏夹还是空的，先去商品页收藏商品吧。
          </p>
        ) : (
          <>
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm text-muted-foreground">
                已选 {draftIds.length} / {candidates.length} 件
              </span>
              <Button variant="outline" size="sm" onClick={toggleAll}>
                {allSelected ? "取消全选" : "全选"}
              </Button>
            </div>
            <div className="grid max-h-[50vh] gap-2 overflow-y-auto pr-1">
              {candidates.map((candidate) => (
                <div
                  key={candidate.id}
                  className="flex items-center gap-3 rounded-md border px-3 py-2 text-sm"
                >
                  <Checkbox
                    checked={selectedSet.has(candidate.id)}
                    onCheckedChange={(checked) =>
                      toggleProduct(candidate.id, checked === true)
                    }
                  />
                  {candidate.imageUrl ? (
                    <img
                      src={candidate.imageUrl}
                      alt={candidate.name}
                      className="size-8 shrink-0 rounded object-cover"
                    />
                  ) : null}
                  <span className="min-w-0 truncate">{candidate.name}</span>
                </div>
              ))}
            </div>
          </>
        )}
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">取消</Button>
          </DialogClose>
          <Button onClick={handleConfirm}>确定</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default ComboProductPickerDialog
