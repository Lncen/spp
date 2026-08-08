export function formatValue(value: unknown): string {
  if (typeof value === "string") {
    return value
  }
  return JSON.stringify(value)
}

export function parseValue(input: string): unknown {
  try {
    return JSON.parse(input)
  } catch {
    return input
  }
}
