export function formatBalance(value?: string | null): string {
  return value == null ? "—" : Number(value).toFixed(2)
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "—"
  return new Date(value).toLocaleString("zh-CN")
}
