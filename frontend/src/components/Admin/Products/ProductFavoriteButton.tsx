import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Heart } from "lucide-react"

import { ProductFavoritesService } from "@/client"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import { cn } from "@/lib/utils"
import { handleError } from "@/utils"

interface ProductFavoriteButtonProps {
  productId: string
}

/**
 * 商品列表行内收藏按钮：收藏状态取自「我的收藏」列表缓存，点击即切换。
 */
export const ProductFavoriteButton = ({
  productId,
}: ProductFavoriteButtonProps) => {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const { data } = useQuery({
    queryKey: ["my-favorites"],
    queryFn: () => ProductFavoritesService.readMyFavorites({ limit: 100 }),
  })
  const favorited = (data?.data ?? []).some(
    (item) => item.product_id === productId,
  )

  const mutation = useMutation({
    mutationFn: async () => {
      if (favorited) {
        await ProductFavoritesService.deleteMyFavorite({ productId })
        return "已取消收藏"
      }
      await ProductFavoritesService.createMyFavorite({
        requestBody: { product_id: productId },
      })
      return "已加入收藏"
    },
    onSuccess: (message) => {
      showSuccessToast(message)
      queryClient.invalidateQueries({ queryKey: ["my-favorites"] })
    },
    onError: handleError.bind(showErrorToast),
  })

  return (
    <Button
      variant="ghost"
      size="icon-sm"
      title={favorited ? "取消收藏" : "收藏商品"}
      aria-label={favorited ? "取消收藏" : "收藏商品"}
      disabled={mutation.isPending}
      onClick={() => mutation.mutate()}
    >
      <Heart
        className={cn(
          "size-4",
          favorited && "fill-destructive text-destructive",
        )}
      />
    </Button>
  )
}

export default ProductFavoriteButton
