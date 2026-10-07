/**
 * 链接提取：下单参数类型为「链接提取」(input_type=13) 时，
 * 从用户粘贴的整段文本里取出 http/https 链接作为参数值。
 */
const LINK_PATTERN = /https?:\/\/[^\s"'<>，。；;、]+/gi

export const extractLinks = (value: string): string[] =>
  value.match(LINK_PATTERN) ?? []
