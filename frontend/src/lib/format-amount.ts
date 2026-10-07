/**
 * 金额展示：按后端金额精度格式化后去掉尾部多余的 0。
 */
export const formatAmount = (value: string | number, precision = 7): string => {
  const fixed = Number(value).toFixed(precision)
  return fixed.replace(/\.?0+$/, "")
}

/**
 * 随机数量取值：在 [min, max] 内取 purchaseStep 的整数倍。
 */
export const randomQuantityInRange = (
  min: number,
  max: number,
  step: number,
): number => {
  const safeStep = Math.max(1, Math.trunc(step) || 1)
  const first = Math.ceil(min / safeStep) * safeStep
  const last = Math.floor(max / safeStep) * safeStep
  if (first > last) return first
  const count = Math.floor((last - first) / safeStep) + 1
  return first + Math.floor(Math.random() * count) * safeStep
}
