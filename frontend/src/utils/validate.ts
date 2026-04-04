/**
 * 表单验证工具函数
 */

/**
 * 验证邮箱格式
 */
export function isEmail(value: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(value)
}

/**
 * 验证手机号格式（中国大陆）
 */
export function isPhone(value: string): boolean {
  const phoneRegex = /^1[3-9]\d{9}$/
  return phoneRegex.test(value)
}

/**
 * 验证 URL 格式
 */
export function isUrl(value: string): boolean {
  try {
    new URL(value)
    return true
  } catch {
    return false
  }
}

/**
 * 验证是否为非空字符串
 */
export function isNotEmpty(value: unknown): boolean {
  if (typeof value === 'string') {
    return value.trim().length > 0
  }
  return value !== null && value !== undefined
}

/**
 * 验证长度范围
 */
export function isLength(value: string, min: number, max: number): boolean {
  const length = value.length
  return length >= min && length <= max
}

/**
 * 验证是否为数字
 */
export function isNumber(value: unknown): boolean {
  return typeof value === 'number' && !isNaN(value)
}

/**
 * 验证是否为整数
 */
export function isInteger(value: unknown): boolean {
  return isNumber(value) && Number.isInteger(value)
}

/**
 * 验证是否为正整数
 */
export function isPositiveInteger(value: unknown): boolean {
  return isInteger(value) && (value as number) > 0
}

/**
 * 验证数组是否非空
 */
export function isNonEmptyArray(value: unknown): boolean {
  return Array.isArray(value) && value.length > 0
}

/**
 * 验证文件类型
 */
export function isValidFileType(fileName: string, allowedTypes: string[]): boolean {
  const extension = fileName.split('.').pop()?.toLowerCase() || ''
  return allowedTypes.includes(extension)
}

/**
 * 验证文件大小
 */
export function isValidFileSize(fileSize: number, maxSizeMB: number): boolean {
  return fileSize <= maxSizeMB * 1024 * 1024
}
