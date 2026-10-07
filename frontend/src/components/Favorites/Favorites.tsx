import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { Heart, Layers } from "lucide-react"
import { useState } from "react"

import { ProductFavoritesService } from "@/client"
import ComboFormDialog from "@/components/Combos/ComboFormDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

export const Favorites = () => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [comboOpen, setComboOpen] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ["my-favorites"],
    queryFn: () => ProductFavoritesService.readMyFavorites({ limit: 100 }),
  })

  const favorites = data?.data ?? []

  const removeMutation = useMutation({
    mutationFn: (productId: string) =>
      ProductFavoritesService.deleteMyFavorite({ productId }),
    onSuccess: () => {
      showSuccessToast("已取消收藏")
      queryClient.invalidateQueries({ queryKey: ["my-favorites"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  const toggleSelected = (productId: string, checked: boolean) => {
    setSelectedIds((current) =>
      checked
        ? [...current, productId]
        : current.filter((id) => id !== productId),
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight">我的收藏</h2>
          <p className="text-muted-foreground">
            勾选商品保存为组合，之后可以一键组合下单
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted-foreground">
            已选 {selectedIds.length} 件
          </span>
          <Button
            variant="outline"
            disabled={favorites.length === 0}
            onClick={() =>
              setSelectedIds(
                selectedIds.length === favorites.length
                  ? []
                  : favorites.map((item) => item.product_id),
              )
            }
          >
            {selectedIds.length === favorites.length && favorites.length > 0
              ? "取消全选"
              : "全选"}
          </Button>
          <Button
            disabled={selectedIds.length === 0}
            onClick={() => setComboOpen(true)}
          >
            <Layers className="mr-2 size-4" />
            保存为组合
          </Button>
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">加载收藏…</p>
      ) : favorites.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <Heart className="size-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              还没有收藏商品，去商品页挑选吧。
            </p>
            <Button asChild variant="outline">
              <Link to="/products">去商品管理</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-2">
          {favorites.map((favorite) => (
            <div
              key={favorite.id}
              className="flex items-center gap-3 rounded-md border px-3 py-2"
            >
              <Checkbox
                checked={selectedIds.includes(favorite.product_id)}
                onCheckedChange={(checked) =>
                  toggleSelected(favorite.product_id, checked === true)
                }
              />
              {favorite.image_url ? (
                <img
                  src={favorite.image_url}
                  alt={favorite.product_name}
                  className="size-10 shrink-0 rounded object-cover"
                />
              ) : (
                <div className="flex size-10 shrink-0 items-center justify-center rounded bg-muted text-[10px] text-muted-foreground">
                  无图
                </div>
              )}
              <span className="min-w-0 flex-1 truncate">
                {favorite.product_name}
              </span>
              {favorite.is_closed && (
                <Badge variant="secondary">已关闭下单</Badge>
              )}
              <Button
                variant="ghost"
                size="sm"
                disabled={removeMutation.isPending}
                onClick={() => removeMutation.mutate(favorite.product_id)}
              >
                取消收藏
              </Button>
            </div>
          ))}
        </div>
      )}

      <ComboFormDialog
        open={comboOpen}
        onOpenChange={setComboOpen}
        initialProductIds={selectedIds}
      />
    </div>
  )
}

export default Favorites
