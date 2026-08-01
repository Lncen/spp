export const PRODUCT_TYPE_OPTIONS = [
  { value: 1, label: "普通商品" },
  { value: 2, label: "卡密" },
  { value: 3, label: "礼品卡" },
  { value: 4, label: "数字内容" },
  { value: 5, label: "服务" },
  { value: 6, label: "课程" },
  { value: 7, label: "游戏道具" },
  { value: 8, label: "其他" },
] as const

export const PRODUCT_STATUS_OPTIONS = [
  { value: 1, label: "待审核" },
  { value: 2, label: "已拒绝" },
  { value: 3, label: "可售" },
  { value: 5, label: "已下架" },
  { value: 6, label: "已撤回" },
  { value: 7, label: "已通过" },
  { value: 8, label: "已售罄" },
] as const

export const SOURCE_TYPE_OPTIONS = [
  { value: 1, label: "供应商" },
  { value: 2, label: "本地" },
  { value: 3, label: "跨境" },
  { value: 4, label: "UGC" },
  { value: 5, label: "联合运营" },
  { value: 6, label: "API 接入" },
  { value: 7, label: "人工" },
  { value: 8, label: "分销" },
] as const

export const REDEEM_TYPE_OPTIONS = [
  { value: 1, label: "自动发货" },
  { value: 2, label: "手动发货" },
  { value: 3, label: "API 自动" },
] as const

export const INPUT_TYPE_OPTIONS = [
  { value: 1, label: "文本" },
  { value: 2, label: "多行文本" },
  { value: 3, label: "下拉选择" },
  { value: 4, label: "密码" },
  { value: 5, label: "多选" },
  { value: 6, label: "数字" },
  { value: 7, label: "数量" },
  { value: 8, label: "数量下拉" },
  { value: 9, label: "开关" },
  { value: 10, label: "QQ 号" },
  { value: 11, label: "手机号" },
  { value: 12, label: "邮箱" },
  { value: 13, label: "链接提取" },
  { value: 14, label: "ID 提取" },
  { value: 15, label: "帖子 ID" },
] as const

export const PRODUCT_STATUS_BADGE_VARIANT: Record<
  number,
  "default" | "secondary" | "destructive" | "outline"
> = {
  1: "secondary",
  2: "destructive",
  3: "default",
  5: "outline",
  6: "outline",
  7: "default",
  8: "secondary",
}

export function productTypeLabel(value: number): string {
  return (
    PRODUCT_TYPE_OPTIONS.find((option) => option.value === value)?.label ??
    String(value)
  )
}

export function productStatusLabel(value: number): string {
  return (
    PRODUCT_STATUS_OPTIONS.find((option) => option.value === value)?.label ??
    String(value)
  )
}

export function sourceTypeLabel(value: number): string {
  return (
    SOURCE_TYPE_OPTIONS.find((option) => option.value === value)?.label ??
    String(value)
  )
}
